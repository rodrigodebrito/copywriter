# ============================================================
# ingest.py — Sistema de Ingestão de Documentos
# ============================================================
# Este arquivo percorre as pastas de apostilas e transcrições,
# extrai metadados automaticamente (pela estrutura de pastas + LLM)
# e salva tudo no ChromaDB com embeddings.
#
# Uso:
#   python ingest.py
#
# Estrutura esperada das apostilas:
#   apostilas/
#   ├── terapia/
#   │   ├── constelacao/
#   │   │   └── intro_constelacao.pdf
#   │   └── hipnose/
#   │       └── hipnose_clinica.pdf
#   └── marketing/
#       └── copywriting/
#           └── gatilhos_mentais.pdf
#
# Estrutura esperada dos videos (transcricoes):
#   videos/
#   ├── Fernando Freitas/
#   ├── Luiza Freitas/
#   └── Thamires Hauch/
# ============================================================

import json
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from agno.knowledge.chunking.semantic import SemanticChunking
from agno.knowledge.reader.pdf_reader import PDFReader

# Importa os componentes configurados no agent.py
from agent import knowledge_base, APOSTILAS_DIR, BASE_DIR

load_dotenv()

# ============================================================
# CLASSIFICADOR LLM — Extrai metadados do conteudo do PDF
# ============================================================
# Envia um trecho do PDF para o GPT-4o-mini (barato e rapido)
# e pede para ele classificar o documento.
#
# Retorna um dict com: tema, autor, palavras_chave
# Isso complementa os metadados extraidos das pastas.

def classificar_documento(texto: str) -> dict:
    """
    Usa GPT-4o-mini para extrair metadados de um trecho de texto.

    Envia apenas os primeiros 2000 caracteres para economizar tokens.
    O LLM retorna um JSON com tema, autor e palavras-chave.

    Args:
        texto: Conteudo extraido do PDF

    Returns:
        dict com chaves: tema, autor, palavras_chave
    """
    # Cliente criado aqui (nao no topo) para evitar erro
    # se a API key nao estiver configurada ainda
    client = OpenAI()

    # Pega so os primeiros 2000 caracteres — suficiente para o LLM
    # entender do que se trata o documento, sem gastar tokens demais
    trecho = texto[:2000]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Voce e um classificador de documentos. "
                    "Analise o trecho e retorne um JSON com:\n"
                    '- "tema": tema principal do documento (ex: "funil de vendas")\n'
                    '- "autor": autor se identificavel, senao "desconhecido"\n'
                    '- "palavras_chave": lista com 3-5 palavras-chave relevantes\n'
                    "Responda APENAS com o JSON, sem explicacoes."
                ),
            },
            {
                "role": "user",
                "content": f"Classifique este documento:\n\n{trecho}",
            },
        ],
    )

    return json.loads(response.choices[0].message.content)


# ============================================================
# EXTRAIR METADADOS DAS PASTAS — Categoria e subcategoria
# ============================================================
# A estrutura de pastas define a hierarquia de metadados:
#   apostilas/terapia/constelacao/arquivo.pdf
#              |         |
#           categoria  subcategoria

def extrair_metadata_pasta(caminho_pdf: Path) -> dict:
    """
    Extrai metadados baseado na posicao do arquivo na arvore de pastas.

    Exemplo:
        apostilas/terapia/constelacao/intro.pdf
        -> {"categoria": "terapia", "subcategoria": "constelacao"}

        apostilas/marketing/copy.pdf
        -> {"categoria": "marketing"}

    Args:
        caminho_pdf: Path completo do arquivo PDF

    Returns:
        dict com categoria e subcategoria (se houver)
    """
    # Pega o caminho relativo a partir da pasta apostilas/
    # Ex: terapia/constelacao/intro.pdf
    relativo = caminho_pdf.relative_to(APOSTILAS_DIR)

    # parts = ("terapia", "constelacao", "intro.pdf")
    # Removemos o ultimo item (nome do arquivo)
    partes = relativo.parts[:-1]

    metadata = {}

    if len(partes) >= 1:
        metadata["categoria"] = partes[0]  # Primeiro nivel: terapia, marketing, etc.

    if len(partes) >= 2:
        metadata["subcategoria"] = partes[1]  # Segundo nivel: constelacao, hipnose, etc.

    if len(partes) >= 3:
        # Se tiver mais niveis, junta como "sub_niveis"
        metadata["sub_niveis"] = "/".join(partes[2:])

    return metadata


# ============================================================
# EXTRAIR TEXTO DO PDF — Para enviar ao classificador LLM
# ============================================================

def extrair_texto_pdf(caminho_pdf: Path) -> str:
    """
    Extrai o texto bruto de um PDF usando pypdf.

    Args:
        caminho_pdf: Path do arquivo PDF

    Returns:
        Texto extraido do PDF
    """
    from pypdf import PdfReader

    reader = PdfReader(str(caminho_pdf))
    texto = ""
    for pagina in reader.pages:
        texto += pagina.extract_text() or ""
    return texto


# ============================================================
# INGERIR APOSTILAS — Percorre a pasta e processa cada PDF
# ============================================================

def _ingerir_pdf(pdf_path: Path, i: int, total: int):
    """Ingere um PDF no knowledge base."""
    nome = pdf_path.name
    print(f"[{i}/{total}] Processando PDF: {nome}")

    metadata_pasta = extrair_metadata_pasta(pdf_path)
    print(f"  Pasta -> {metadata_pasta}")

    texto = extrair_texto_pdf(pdf_path)

    if not texto.strip():
        print(f"  AVISO: PDF sem texto extraivel (pode ser escaneado)")
        metadata_llm = {"tema": "nao identificado", "autor": "desconhecido", "palavras_chave": []}
    else:
        print(f"  Classificando com LLM...")
        metadata_llm = classificar_documento(texto)
        print(f"  LLM -> tema: {metadata_llm.get('tema')}, autor: {metadata_llm.get('autor')}")

    metadata_final = {
        "tipo": "apostila",
        **metadata_pasta,
        "tema": metadata_llm.get("tema", ""),
        "autor": metadata_llm.get("autor", "desconhecido"),
        "palavras_chave": ", ".join(metadata_llm.get("palavras_chave", [])),
        "arquivo": nome,
    }

    print(f"  Adicionando ao ChromaDB...")
    knowledge_base.add_content(
        path=str(pdf_path),
        reader=PDFReader(chunking_strategy=SemanticChunking()),
        metadata=metadata_final,
        skip_if_exists=True,
    )
    print(f"  OK!\n")


def _ingerir_txt(txt_path: Path, i: int, total: int):
    """Ingere um TXT no knowledge base."""
    nome = txt_path.name
    print(f"[{i}/{total}] Processando TXT: {nome}")

    metadata_pasta = extrair_metadata_pasta(txt_path)
    print(f"  Pasta -> {metadata_pasta}")

    texto = txt_path.read_text(encoding="utf-8")

    if not texto.strip():
        print(f"  AVISO: TXT vazio — pulando")
        return

    print(f"  Classificando com LLM...")
    metadata_llm = classificar_documento(texto)
    print(f"  LLM -> tema: {metadata_llm.get('tema')}, autor: {metadata_llm.get('autor')}")

    metadata_final = {
        "tipo": "apostila",
        **metadata_pasta,
        "tema": metadata_llm.get("tema", ""),
        "autor": metadata_llm.get("autor", "desconhecido"),
        "palavras_chave": ", ".join(metadata_llm.get("palavras_chave", [])),
        "arquivo": nome,
    }

    print(f"  Adicionando ao ChromaDB...")
    knowledge_base.add_content(
        text_content=texto,
        name=f"apostila-{txt_path.stem}",
        metadata=metadata_final,
        skip_if_exists=True,
    )
    print(f"  OK!\n")


def ingerir_apostilas():
    """
    Percorre todos os PDFs e TXTs em apostilas/ (incluindo subpastas),
    extrai metadados (pastas + LLM) e adiciona ao knowledge base.
    """
    pdfs = list(APOSTILAS_DIR.rglob("*.pdf"))
    txts = list(APOSTILAS_DIR.rglob("*.txt"))
    arquivos = pdfs + txts

    if not arquivos:
        print("Nenhum PDF ou TXT encontrado em apostilas/")
        print(f"Coloque seus arquivos em: {APOSTILAS_DIR}")
        return

    print(f"Encontrados {len(pdfs)} PDFs e {len(txts)} TXTs para processar\n")

    for i, path in enumerate(arquivos, 1):
        if path.suffix.lower() == ".pdf":
            _ingerir_pdf(path, i, len(arquivos))
        else:
            _ingerir_txt(path, i, len(arquivos))

    print("Ingestao de apostilas concluida!")


# ============================================================
# INGERIR TRANSCRICOES — Transcricoes dos videos por autor
# ============================================================
# Por enquanto so prepara a estrutura.
# A transcricao dos videos sera implementada depois.

VIDEOS_DIR = BASE_DIR / "videos"


def ingerir_transcricoes():
    """
    Percorre as pastas de autores em videos/ e adiciona
    transcricoes ao knowledge base com metadata de estilo.

    Metadados para transcricoes sao mais simples:
    - tipo: "transcricao" (para filtrar separado das apostilas)
    - autor: nome da pasta (Fernando Freitas, etc.)

    Aqui NAO precisamos de tema/categoria porque o objetivo
    e capturar o ESTILO do autor, nao o conteudo.
    """
    # Busca arquivos .txt nas pastas dos autores
    txts = list(VIDEOS_DIR.rglob("*.txt"))

    if not txts:
        print("Nenhuma transcricao encontrada em videos/")
        print("(As transcricoes serao geradas pelo modulo de transcricao)")
        return

    print(f"Encontradas {len(txts)} transcricoes para processar\n")

    for i, txt_path in enumerate(txts, 1):
        # O nome da pasta pai e o nome do autor
        # Ex: videos/Fernando Freitas/video1.txt -> autor = "Fernando Freitas"
        autor = txt_path.parent.name

        print(f"[{i}/{len(txts)}] Processando: {txt_path.name} (autor: {autor})")

        metadata = {
            "tipo": "transcricao",
            "autor": autor,
            "arquivo": txt_path.name,
        }

        knowledge_base.add_content(
            path=str(txt_path),
            metadata=metadata,
            skip_if_exists=True,
        )

        print(f"  OK!\n")

    print("Ingestao de transcricoes concluida!")


# ============================================================
# MAIN — Ponto de entrada
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  CopyWriter — Ingestao de Documentos")
    print("=" * 50)
    print()

    print("--- APOSTILAS ---")
    ingerir_apostilas()

    print()

    print("--- TRANSCRICOES ---")
    ingerir_transcricoes()

    print()
    print("Tudo pronto! O knowledge base foi atualizado.")

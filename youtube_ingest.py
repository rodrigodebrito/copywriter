# ============================================================
# youtube_ingest.py — Ingestao de Transcricoes do YouTube
# ============================================================
# Percorre as URLs em youtube_urls.txt, baixa as transcricoes
# (legendas) de cada video via youtube-transcript-api, classifica
# o conteudo com GPT-4o-mini e salva no ChromaDB.
#
# Nao precisa de API key do YouTube — a lib extrai legendas
# publicas diretamente.
#
# Uso:
#   python youtube_ingest.py
#
# Entrada:
#   youtube_urls.txt — uma URL por linha, comentarios com #
#
# Saida:
#   data/youtube/<video_id>.json — transcricao + metadados
#   ChromaDB — embeddings com metadata tipo="youtube"
# ============================================================

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from openai import OpenAI
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

from agent import knowledge_base, BASE_DIR, DB_DIR

load_dotenv()

# ============================================================
# PATHS
# ============================================================
YOUTUBE_DIR = DB_DIR / "youtube"
YOUTUBE_DIR.mkdir(parents=True, exist_ok=True)

URLS_FILE = BASE_DIR / "youtube_urls.txt"


# ============================================================
# EXTRAIR VIDEO ID — Suporta varios formatos de URL do YouTube
# ============================================================

def extrair_video_id(url: str) -> str | None:
    """
    Extrai o ID do video de uma URL do YouTube.

    Formatos suportados:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID

    Returns:
        ID do video (11 caracteres) ou None se invalido
    """
    url = url.strip()

    # Formato youtu.be/VIDEO_ID
    match = re.match(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # Formatos youtube.com
    parsed = urlparse(url)
    if "youtube.com" in parsed.hostname or "youtube" in parsed.hostname:
        # /watch?v=VIDEO_ID
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]

        # /embed/VIDEO_ID ou /shorts/VIDEO_ID
        match = re.match(r"/(embed|shorts|v)/([a-zA-Z0-9_-]{11})", parsed.path)
        if match:
            return match.group(2)

    return None


# ============================================================
# BAIXAR TRANSCRICAO — Prioriza PT, fallback para EN
# ============================================================

def baixar_transcricao(video_id: str) -> dict | None:
    """
    Baixa a transcricao de um video do YouTube.

    Tenta na ordem: pt, pt-BR, en. Se nenhum disponivel,
    tenta qualquer idioma disponivel.

    Returns:
        dict com {texto, idioma, idioma_codigo} ou None se falhar
    """
    api = YouTubeTranscriptApi()

    result = None

    # Tenta fetch direto com idiomas preferenciais
    try:
        result = api.fetch(video_id, languages=["pt", "pt-BR", "en"])
    except Exception:
        pass

    # Fallback: lista as transcricoes disponiveis e busca a primeira
    if result is None:
        try:
            transcript_list = api.list(video_id)
            for transcript in transcript_list:
                try:
                    result = transcript.fetch()
                    break
                except Exception:
                    continue
        except Exception:
            return None

    if result is None:
        return None

    # Junta todos os snippets em texto corrido
    texto = " ".join(
        s.text.replace("\n", " ") for s in result.snippets
    )

    return {
        "texto": texto,
        "idioma": result.language,
        "idioma_codigo": result.language_code,
    }


# ============================================================
# CLASSIFICAR CONTEUDO — GPT-4o-mini extrai tema e keywords
# ============================================================

def classificar_conteudo(texto: str) -> dict:
    """
    Usa GPT-4o-mini para extrair metadados da transcricao.

    Envia os primeiros 2000 caracteres (economiza tokens).
    Retorna: {tema, palavras_chave}
    """
    client = OpenAI()
    trecho = texto[:2000]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Voce e um classificador de conteudo. "
                    "Analise o trecho de transcricao e retorne um JSON com:\n"
                    '- "tema": tema principal (ex: "programacao mental", "autoestima")\n'
                    '- "palavras_chave": lista com 3-5 palavras-chave relevantes\n'
                    "Responda APENAS com o JSON, sem explicacoes."
                ),
            },
            {
                "role": "user",
                "content": f"Classifique esta transcricao:\n\n{trecho}",
            },
        ],
    )

    return json.loads(response.choices[0].message.content)


# ============================================================
# LER URLs — Parse do arquivo youtube_urls.txt
# ============================================================

def ler_urls() -> list[str]:
    """
    Le URLs do arquivo youtube_urls.txt.
    Ignora linhas vazias e comentarios (#).
    """
    if not URLS_FILE.exists():
        return []

    urls = []
    for linha in URLS_FILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        # Ignora vazias e comentarios
        if not linha or linha.startswith("#"):
            continue
        urls.append(linha)

    return urls


# ============================================================
# PROCESSAR URL — Fluxo completo para um video
# ============================================================

def processar_url(url: str) -> bool:
    """
    Processa uma URL do YouTube:
    1. Extrai video ID
    2. Verifica se ja foi processado
    3. Baixa transcricao
    4. Classifica conteudo com LLM
    5. Salva JSON
    6. Ingere no ChromaDB

    Returns:
        True se processou, False se pulou ou falhou
    """
    # 1. Extrair video ID
    video_id = extrair_video_id(url)
    if not video_id:
        print(f"  ERRO: URL invalida — {url}")
        return False

    # 2. Verificar se ja foi processado
    json_path = YOUTUBE_DIR / f"{video_id}.json"
    if json_path.exists():
        # Ja processado — garante que esta no ChromaDB
        print(f"  Ja processado, garantindo ChromaDB...")
        dados = json.loads(json_path.read_text(encoding="utf-8"))
        texto = dados.get("transcricao", "")
        if texto.strip():
            metadata = {
                "tipo": "youtube",
                "tema": dados.get("tema", ""),
                "palavras_chave": dados.get("palavras_chave", ""),
                "url": url,
                "arquivo": json_path.name,
            }
            knowledge_base.add_content(
                text_content=texto,
                name=f"youtube-{video_id}",
                metadata=metadata,
                skip_if_exists=True,
            )
        return False

    # 3. Baixar transcricao
    print(f"  Baixando transcricao...")
    resultado = baixar_transcricao(video_id)
    if not resultado:
        print(f"  ERRO: Nenhuma legenda disponivel")
        return False

    texto = resultado["texto"]
    if not texto.strip():
        print(f"  ERRO: Transcricao vazia")
        return False

    print(f"  Idioma: {resultado['idioma']} ({resultado['idioma_codigo']})")
    print(f"  Tamanho: {len(texto)} caracteres")

    # 4. Classificar conteudo
    print(f"  Classificando com LLM...")
    classificacao = classificar_conteudo(texto)
    tema = classificacao.get("tema", "")
    palavras_chave = classificacao.get("palavras_chave", [])
    print(f"  Tema: {tema}")
    print(f"  Palavras-chave: {palavras_chave}")

    # 5. Salvar JSON
    dados = {
        "tipo": "youtube",
        "video_id": video_id,
        "url": url,
        "idioma": resultado["idioma"],
        "idioma_codigo": resultado["idioma_codigo"],
        "tema": tema,
        "palavras_chave": palavras_chave,
        "transcricao": texto,
    }

    json_path.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Salvo em: {json_path.name}")

    # 6. Ingerir no ChromaDB
    print(f"  Adicionando ao ChromaDB...")
    metadata = {
        "tipo": "youtube",
        "tema": tema,
        "palavras_chave": ", ".join(palavras_chave) if isinstance(palavras_chave, list) else str(palavras_chave),
        "url": url,
        "arquivo": json_path.name,
    }

    knowledge_base.add_content(
        text_content=texto,
        name=f"youtube-{video_id}",
        metadata=metadata,
        skip_if_exists=True,
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("  CopyWriter — Ingestao do YouTube")
    print("=" * 50)
    print()

    urls = ler_urls()

    if not urls:
        if not URLS_FILE.exists():
            print(f"Arquivo nao encontrado: {URLS_FILE}")
            print("Crie o arquivo youtube_urls.txt com uma URL por linha.")
        else:
            print("Nenhuma URL encontrada em youtube_urls.txt")
        return

    print(f"Encontradas {len(urls)} URLs para processar\n")

    total_processados = 0

    for i, url in enumerate(urls, 1):
        video_id = extrair_video_id(url)
        label = video_id or url[:50]
        print(f"[{i}/{len(urls)}] {label}")

        processou = processar_url(url)
        if processou:
            total_processados += 1
            print(f"  OK!\n")
            # Delay entre requisicoes para nao ser bloqueado
            if i < len(urls):
                time.sleep(1)
        else:
            print()

    print(f"{'=' * 50}")
    print(f"  Concluido: {total_processados} novos videos processados")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

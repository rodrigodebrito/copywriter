# ============================================================
# profiles.py — Gerador de Perfis de Estilo dos Creators
# ============================================================
# Analisa TODAS as transcricoes de cada creator e gera um
# "DNA de estilo" completo — um perfil persistente que o agente
# consulta para clonar o creator sem re-analisar toda vez.
#
# O perfil captura 10 pontos de clonagem com exemplos reais:
# tom, energia, linguajar, bordoes, estrutura, ritmo,
# analogias, emocao, hooks e CTAs.
#
# Uso:
#   python profiles.py
#
# Saida:
#   data/profiles/<autor>.json — perfil completo
#   ChromaDB — embedding com metadata tipo="perfil"
# ============================================================

import json
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from agent import knowledge_base, VIDEOS_DIR, DB_DIR

load_dotenv()

# ============================================================
# PATHS
# ============================================================
PROFILES_DIR = DB_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# PROMPT DE ANALISE — Extrai o DNA completo do creator
# ============================================================

PROMPT_ANALISE = """Voce e um especialista em analise de estilo de comunicacao. Sua missao e criar o PERFIL DE CLONAGEM completo de um creator a partir das transcricoes dos videos dele.

Analise TODAS as transcricoes abaixo e extraia um perfil DETALHADO e PRATICO que permita a qualquer pessoa escrever EXATAMENTE como esse creator fala.

## O QUE ANALISAR (10 pontos de clonagem)

Para cada ponto, de:
- Uma descricao clara do padrao
- 2-3 exemplos REAIS extraidos das transcricoes (copie trechos exatos)
- Regras especificas para replicar

### 1. TOM DE VOZ
Como ele se posiciona? (autoritario, amigo, provocativo, acolhedor, professor, mentor...)
Fala de cima pra baixo ou de igual pra igual? E serio ou descontraido?

### 2. ENERGIA E INTENSIDADE
O ritmo e acelerado ou calmo? Usa exclamacoes? Faz pausas dramaticas?
A energia e alta (motivacional) ou baixa (reflexiva)?

### 3. LINGUAJAR E VOCABULARIO
Usa girias? Quais? Fala palavrao? Usa termos tecnicos ou populares?
O vocabulario e simples ou rebuscado? Mistura formal com informal?

### 4. BORDOES E EXPRESSOES REPETIDAS
Quais frases ele repete frequentemente? Tem algum "cacoete" verbal?
Expressoes que sao a "marca registrada" dele.

### 5. ESTRUTURA DE ARGUMENTACAO
Como ele constroi um argumento? Comeca com pergunta? Com afirmacao forte?
Usa historias pessoais? Dados? Exemplos do dia a dia?

### 6. RITMO DAS FRASES
Frases curtas e diretas? Ou longas e explicativas?
Alterna entre curtas e longas? Usa repeticao pra enfatizar?

### 7. ANALOGIAS E METAFORAS
Que tipo de comparacoes ele faz? De que universo vem as analogias?
(cotidiano, esporte, guerra, natureza, negocios...)

### 8. CONEXAO EMOCIONAL
Como ele conecta com a audiencia? Usa "voce"? Conta historias pessoais?
Faz o ouvinte se sentir entendido? Usa empatia ou provocacao?

### 9. ESTILO DE HOOKS (ABERTURA)
Como ele abre os videos? Com pergunta? Afirmacao chocante? Promessa?
Qual o padrao de gancho que ele usa pra prender atencao?

### 10. ESTILO DE CTA (FECHAMENTO)
Como ele encerra? Pede pra seguir? Faz convite? Deixa reflexao?
Qual o padrao de chamada pra acao?

## FORMATO DE SAIDA

Retorne um JSON com esta estrutura exata:
{
  "autor": "Nome do Creator",
  "resumo_estilo": "Descricao em 2-3 frases do estilo geral",
  "tom_de_voz": {
    "descricao": "...",
    "exemplos": ["trecho real 1", "trecho real 2"],
    "regras": ["regra 1", "regra 2"]
  },
  "energia": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "linguajar": {
    "descricao": "...",
    "girias_e_expressoes": ["lista de girias e expressoes usadas"],
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "bordoes": {
    "descricao": "...",
    "lista": ["bordao 1", "bordao 2"],
    "exemplos": ["...", "..."]
  },
  "estrutura": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "ritmo": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "analogias": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "emocao": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "hooks": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  },
  "cta": {
    "descricao": "...",
    "exemplos": ["...", "..."],
    "regras": ["...", "..."]
  }
}

IMPORTANTE:
- Use APENAS trechos reais das transcricoes como exemplos
- Seja ESPECIFICO — nada generico. Se ele fala "Po", "Mano", "Sacou?" — inclua essas palavras exatas
- As regras devem ser PRATICAS: "Comece frases com...", "Use a expressao X quando...", "Nunca use Y..."
- Responda APENAS com o JSON, sem explicacoes antes ou depois"""


# ============================================================
# COLETAR TRANSCRICOES — Le todos os JSONs de um creator
# ============================================================

def coletar_transcricoes(autor_dir: Path) -> str:
    """
    Le todas as transcricoes JSON de um creator e junta em um texto so.
    Separa cada video com marcadores para o GPT entender.
    """
    textos = []
    for json_path in sorted(autor_dir.glob("*.json")):
        dados = json.loads(json_path.read_text(encoding="utf-8"))
        texto = dados.get("transcricao", "")
        if texto.strip():
            textos.append(f"--- VIDEO: {json_path.stem} ---\n{texto}")

    return "\n\n".join(textos)


# ============================================================
# GERAR PERFIL — Envia transcricoes pro GPT e recebe o perfil
# ============================================================

def gerar_perfil(autor: str, transcricoes: str) -> dict:
    """
    Envia todas as transcricoes de um creator para o GPT
    e recebe o perfil de clonagem completo em JSON.
    """
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT_ANALISE},
            {
                "role": "user",
                "content": (
                    f"Crie o perfil de clonagem completo do creator: {autor}\n\n"
                    f"Transcricoes:\n\n{transcricoes}"
                ),
            },
        ],
    )

    return json.loads(response.choices[0].message.content)


# ============================================================
# FORMATAR PERFIL PARA TEXTO — Converte JSON em texto legivel
# para embeddings melhores no ChromaDB
# ============================================================

def perfil_para_texto(perfil: dict) -> str:
    """
    Converte o perfil JSON em texto corrido otimizado para embeddings.
    O ChromaDB busca por similaridade semantica — texto corrido
    funciona melhor que JSON puro para isso.
    """
    autor = perfil.get("autor", "Desconhecido")
    resumo = perfil.get("resumo_estilo", "")

    linhas = [
        f"PERFIL DE ESTILO: {autor}",
        f"Resumo: {resumo}",
        "",
    ]

    campos = [
        ("tom_de_voz", "TOM DE VOZ"),
        ("energia", "ENERGIA E INTENSIDADE"),
        ("linguajar", "LINGUAJAR E VOCABULARIO"),
        ("bordoes", "BORDOES E EXPRESSOES"),
        ("estrutura", "ESTRUTURA DE ARGUMENTACAO"),
        ("ritmo", "RITMO DAS FRASES"),
        ("analogias", "ANALOGIAS E METAFORAS"),
        ("emocao", "CONEXAO EMOCIONAL"),
        ("hooks", "ESTILO DE HOOKS"),
        ("cta", "ESTILO DE CTA"),
    ]

    for campo, titulo in campos:
        dados = perfil.get(campo, {})
        if not dados:
            continue

        linhas.append(f"## {titulo}")
        linhas.append(dados.get("descricao", ""))

        # Girias (campo especifico do linguajar)
        girias = dados.get("girias_e_expressoes", [])
        if girias:
            linhas.append(f"Girias e expressoes: {', '.join(girias)}")

        # Bordoes (campo especifico)
        lista = dados.get("lista", [])
        if lista:
            linhas.append(f"Bordoes: {', '.join(lista)}")

        # Exemplos reais
        exemplos = dados.get("exemplos", [])
        if exemplos:
            linhas.append("Exemplos reais:")
            for ex in exemplos:
                linhas.append(f'  - "{ex}"')

        # Regras de clonagem
        regras = dados.get("regras", [])
        if regras:
            linhas.append("Regras:")
            for r in regras:
                linhas.append(f"  - {r}")

        linhas.append("")

    return "\n".join(linhas)


# ============================================================
# SALVAR E INGERIR — Salva JSON + texto no ChromaDB
# ============================================================

def salvar_perfil(autor: str, perfil: dict, force: bool = False) -> bool:
    """
    Salva o perfil em JSON e ingere no ChromaDB.

    Args:
        autor: Nome do creator
        perfil: Dict com o perfil completo
        force: Se True, regenera mesmo se ja existe

    Returns:
        True se salvou/ingeriu, False se ja existia
    """
    json_path = PROFILES_DIR / f"{autor}.json"

    if json_path.exists() and not force:
        print(f"  Perfil ja existe. Use force=True para regenerar.")
        # Garante que esta no ChromaDB
        texto = perfil_para_texto(
            json.loads(json_path.read_text(encoding="utf-8"))
        )
        metadata = {
            "tipo": "perfil",
            "autor": autor,
            "arquivo": json_path.name,
        }
        knowledge_base.add_content(
            text_content=texto,
            name=f"perfil-{autor}",
            metadata=metadata,
            skip_if_exists=True,
        )
        return False

    # Salva JSON
    json_path.write_text(
        json.dumps(perfil, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Salvo em: {json_path}")

    # Converte para texto e ingere no ChromaDB
    texto = perfil_para_texto(perfil)
    metadata = {
        "tipo": "perfil",
        "autor": autor,
        "arquivo": json_path.name,
    }
    knowledge_base.add_content(
        text_content=texto,
        name=f"perfil-{autor}",
        metadata=metadata,
        skip_if_exists=not force,
    )
    print(f"  Adicionado ao ChromaDB")

    return True


# ============================================================
# MAIN
# ============================================================

def main(force: bool = False):
    """
    Gera perfis de estilo para todos os creators.

    Args:
        force: Se True, regenera todos os perfis (mesmo os existentes)
    """
    print("=" * 50)
    print("  CopyWriter — Geracao de Perfis de Creators")
    print("=" * 50)
    print()

    if not VIDEOS_DIR.exists():
        print("Pasta videos/ nao encontrada.")
        return

    autores = [p for p in sorted(VIDEOS_DIR.iterdir()) if p.is_dir()]

    if not autores:
        print("Nenhum creator encontrado em videos/")
        return

    print(f"Encontrados {len(autores)} creators\n")

    total_gerados = 0

    for autor_dir in autores:
        autor = autor_dir.name
        json_path = PROFILES_DIR / f"{autor}.json"

        print(f"[{autor}]")

        # Verifica se ja tem perfil
        if json_path.exists() and not force:
            print(f"  Perfil ja existe — garantindo ChromaDB...")
            perfil = json.loads(json_path.read_text(encoding="utf-8"))
            salvar_perfil(autor, perfil, force=False)
            print()
            continue

        # Coleta transcricoes
        transcricoes = coletar_transcricoes(autor_dir)
        if not transcricoes.strip():
            print(f"  Nenhuma transcricao encontrada — pulando")
            print()
            continue

        print(f"  Transcricoes: {len(transcricoes)} caracteres")
        print(f"  Analisando estilo com GPT...")

        # Gera perfil
        perfil = gerar_perfil(autor, transcricoes)
        resumo = perfil.get("resumo_estilo", "")
        print(f"  Resumo: {resumo[:100]}...")

        # Salva e ingere
        salvar_perfil(autor, perfil, force=True)
        total_gerados += 1
        print()

    print(f"{'=' * 50}")
    print(f"  Concluido: {total_gerados} perfis gerados")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    if force:
        print("Modo FORCE: regenerando todos os perfis\n")
    main(force=force)

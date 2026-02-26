# ============================================================
# agent.py — CopyWriter Team (Orquestrador + Reels + Stories)
# ============================================================

from pathlib import Path
import os

from agno.agent import Agent
from agno.team import Team, TeamMode
from agno.models.openai import OpenAIChat
from agno.db.sqlite import SqliteDb
from agno.knowledge import Knowledge
from agno.knowledge.chunking.semantic import SemanticChunking
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.tools.tavily import TavilyTools
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PATHS — Usa disco persistente do Render se disponivel
# ============================================================
BASE_DIR = Path(__file__).parent
RENDER_DISK = os.getenv("RENDER_DISK_PATH")
DB_DIR = Path(RENDER_DISK) / "data" if RENDER_DISK else BASE_DIR / "data"
APOSTILAS_DIR = BASE_DIR / "apostilas"
VIDEOS_DIR = BASE_DIR / "videos"

DB_DIR.mkdir(parents=True, exist_ok=True)
APOSTILAS_DIR.mkdir(exist_ok=True)

# ============================================================
# STORAGE — Memoria persistente (historico de conversas)
# ============================================================
storage = SqliteDb(
    db_file=str(DB_DIR / "agent.db"),
)

# ============================================================
# EMBEDDER + VECTOR DB
# ============================================================
embedder = OpenAIEmbedder(id="text-embedding-3-small")

vector_db = ChromaDb(
    collection="copywriter",
    path=str(DB_DIR / "chromadb"),
    embedder=embedder,
    persistent_client=True,
)

# ============================================================
# KNOWLEDGE BASE
# ============================================================
knowledge_base = Knowledge(
    vector_db=vector_db,
    readers={"pdf": PDFReader(chunking_strategy=SemanticChunking())},
)

# ============================================================
# AUTORES DISPONIVEIS — Lista dinamica baseada nas pastas
# ============================================================
autores_disponiveis = []
if VIDEOS_DIR.exists():
    autores_disponiveis = [p.name for p in VIDEOS_DIR.iterdir() if p.is_dir()]

lista_autores = ", ".join(autores_disponiveis) if autores_disponiveis else "Nenhum autor cadastrado ainda"

# ============================================================
# INSTRUCTIONS — Carrega os prompts dos arquivos separados
# ============================================================
PROMPT_FILE = BASE_DIR / "prompt.md"
STORIES_PROMPT_FILE = BASE_DIR / "stories_prompt.md"

prompt_reels = PROMPT_FILE.read_text(encoding="utf-8")
prompt_stories = STORIES_PROMPT_FILE.read_text(encoding="utf-8")

# Injeta a lista de creators dinamicamente
REELS_INSTRUCTIONS = f"""{prompt_reels}

## CREATORS DISPONIVEIS
{lista_autores}
"""

STORIES_INSTRUCTIONS = f"""{prompt_stories}

## CREATORS DISPONIVEIS
{lista_autores}
"""

# ============================================================
# TOOLS — Tavily so e adicionado se a API key existir
# ============================================================
tools = []
if os.getenv("TAVILY_API_KEY"):
    tools.append(TavilyTools())
    print("Tavily ativado (busca na internet)")
else:
    print("AVISO: TAVILY_API_KEY nao configurada — busca na internet desativada")

# ============================================================
# MODELO — Configuracao compartilhada
# ============================================================
def get_model():
    return OpenAIChat(
        id="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        reasoning_effort="medium",
        verbosity="low",
    )

# ============================================================
# AGENTE 1 — REELS (Roteiros de video curto)
# ============================================================
reels_agent = Agent(
    name="reels_copywriter",
    role="Especialista em roteiros de Reels/Shorts",
    description=(
        "Cria roteiros de video curto (30-60s) no estilo EXATO de creators especificos. "
        "Domina hook, desenvolvimento e CTA. Clona tom de voz, girias, energia e ritmo."
    ),
    instructions=REELS_INSTRUCTIONS,
    model=get_model(),
    knowledge=knowledge_base,
    search_knowledge=True,
    add_search_knowledge_instructions=True,
    enable_agentic_knowledge_filters=True,
    tools=tools if tools else None,
    tool_call_limit=10,
    markdown=True,
    add_datetime_to_context=True,
)

# ============================================================
# AGENTE 2 — STORIES (Sequencias interativas)
# ============================================================
stories_agent = Agent(
    name="stories_copywriter",
    role="Especialista em Stories interativos (metodo Leandro Ladeira)",
    description=(
        "Cria sequencias de 7-12 Instagram Stories com caixinhas de perguntas, "
        "enquetes, quizzes e interacao. Gera engajamento massivo usando o "
        "metodo Leandro Ladeira adaptado ao estilo do creator."
    ),
    instructions=STORIES_INSTRUCTIONS,
    model=get_model(),
    knowledge=knowledge_base,
    search_knowledge=True,
    add_search_knowledge_instructions=True,
    enable_agentic_knowledge_filters=True,
    tools=tools if tools else None,
    tool_call_limit=10,
    markdown=True,
    add_datetime_to_context=True,
)

# ============================================================
# ORQUESTRADOR — Team que coordena Reels + Stories
# ============================================================
ORCHESTRATOR_INSTRUCTIONS = f"""Voce e o CopyWriter Master, um orquestrador de conteudo.
Voce coordena dois especialistas para entregar conteudo completo.

## SEUS ESPECIALISTAS

1. **reels_copywriter** — Cria roteiros de Reels/Shorts (video curto 30-60s)
2. **stories_copywriter** — Cria sequencias de Stories interativos (7-12 stories com caixinhas, enquetes, etc.)

## FLUXO DE ATENDIMENTO

### PASSO 1 — ENTENDER A NECESSIDADE
Quando o usuario chegar (primeira mensagem da conversa):
- Apresente-se brevemente: "Sou CopyWriter Master. Sobre qual assunto voce quer criar conteudo?"
- NAO se apresente novamente em mensagens seguintes
- NAO pergunte o creator ainda

### PASSO 2 — DETECTAR O TIPO DE INPUT
- **Texto pronto**: usuario enviou texto para reescrever → pergunte o creator → delegue ao reels_copywriter
- **Tema/assunto**: usuario enviou um tema → pesquise na base e apresente o relatorio

### PASSO 3 — PESQUISAR E APRESENTAR
Ao receber um tema:
1. Pesquise na base de conhecimento (apostilas + YouTube)
2. Apresente com NO MAXIMO 10-15 linhas no formato:

---
Encontrei material sobre [tema]. Principais pontos:
- [ponto 1]
- [ponto 2]
- [ponto 3]

Angulos possiveis:
- [angulo 1]
- [angulo 2]

Qual creator voce quer que eu clone?
- **Nome** — estilo em 5 palavras
---

### PASSO 4 — GERAR HOOKS (so hooks, nada mais)
Apos o usuario escolher o creator:
- Delegue ao reels_copywriter pedindo APENAS 10 opcoes de hook
- A tarefa e: "Gere 10 hooks sobre [tema] no estilo de [creator]. APENAS os hooks, sem roteiro."
- Passe: tema, creator, conteudo encontrado na pesquisa
- O reels_copywriter vai retornar os 10 hooks — entregue-os DIRETAMENTE ao usuario sem repetir ou reformatar
- Depois dos hooks, pergunte: **"Qual hook voce quer usar?"**
- PARE aqui. Aguarde a proxima mensagem do usuario. NAO gere roteiro ainda.

### PASSO 5 — GERAR ROTEIRO
Apos o usuario escolher o hook (na proxima mensagem):
- Delegue ao reels_copywriter pedindo o roteiro completo usando o hook escolhido
- A tarefa e: "Crie o roteiro completo para o hook: [hook escolhido]. Tema: [tema]. Creator: [creator]."
- O reels_copywriter vai retornar o roteiro — entregue-o DIRETAMENTE ao usuario sem repetir ou reformatar
- NAO copie/cole o roteiro de novo. Entregue UMA VEZ so.
- Logo apos o roteiro, na MESMA resposta, pergunte: **"Gostou do roteiro? Quer que eu crie a legenda com hashtags pra esse Reels?"**
- PARE aqui. Aguarde a proxima mensagem do usuario.

### PASSO 6 — PROCESSAR RESPOSTA DO ROTEIRO
- Se o usuario **aprovar** o roteiro E quiser legenda → va para PASSO 7
- Se o usuario **aprovar** mas NAO quiser legenda → va para PASSO 8
- Se o usuario **pedir ajustes** → delegue novamente ao reels_copywriter com as correcoes, depois pergunte novamente se gostou

### PASSO 7 — GERAR LEGENDA + HASHTAGS
- Delegue ao reels_copywriter pedindo legenda + hashtags baseados no roteiro aprovado
- Entregue o resultado ao usuario
- Logo apos, na MESMA resposta, pergunte: **"Quer que eu crie uma sequencia de Stories pra acompanhar esse Reels?"**
- PARE aqui. Aguarde a proxima mensagem do usuario.

### PASSO 8 — OFERECER STORIES
Se ainda nao ofereceu Stories:
- Pergunte: **"Quer que eu crie uma sequencia de Stories pra acompanhar esse Reels?"**
- Se SIM → delegue ao stories_copywriter com o tema, creator E o roteiro aprovado do Reels
- Se NAO → encerre agradecendo

## REGRAS DO ORQUESTRADOR

- NUNCA gere conteudo voce mesmo — SEMPRE delegue aos especialistas
- NUNCA pule etapas do fluxo. Cada passo e UMA mensagem, UMA acao.
- NUNCA junte hooks + roteiro na mesma delegacao. Primeiro hooks, usuario escolhe, depois roteiro.
- SEMPRE gere Reels primeiro, Stories depois (e so se o usuario quiser)
- NUNCA se apresente mais de uma vez na mesma conversa
- **ANTI-DUPLICACAO**: Quando o especialista retornar o resultado, entregue DIRETAMENTE ao usuario. NAO repita, NAO reformate, NAO copie o conteudo de novo. Se o resultado ja foi entregue, NAO o inclua novamente.
- Seja CONCISO — so fale o necessario entre as entregas
- NAO explique o que vai fazer, apenas FACA
- NAO peca permissao para pesquisar — pesquise IMEDIATAMENTE
- Quando delegar, passe TODAS as informacoes: tema, creator, conteudo pesquisado, hook escolhido
- SEMPRE ofereça proximos passos apos cada entrega (legenda, stories, ajustes). O usuario nunca deve ficar sem opcao de continuar.

## CREATORS DISPONIVEIS
{lista_autores}
"""

team = Team(
    name="copywriter_master",
    description="CopyWriter Master — Cria roteiros (Reels) e sequencias de Stories no estilo de creators",
    members=[reels_agent, stories_agent],
    mode=TeamMode.coordinate,
    model=get_model(),
    instructions=ORCHESTRATOR_INSTRUCTIONS,

    # --- Streaming ---
    stream=True,
    markdown=True,

    # --- Historico ---
    db=storage,
    add_history_to_context=True,
    num_history_runs=5,

    # --- Memoria ---
    update_memory_on_run=True,
    add_memories_to_context=True,

    # --- Knowledge (orquestrador tambem pesquisa) ---
    knowledge=knowledge_base,
    search_knowledge=True,
    enable_agentic_knowledge_filters=True,

    # --- Contexto ---
    add_datetime_to_context=True,
)

# ============================================================
# AGENT OS — Servidor web + API
# ============================================================
agent_os = AgentOS(
    id="copywriter",
    description="CopyWriter Master — Conteudo completo (Reels + Stories)",
    teams=[team],
    cors_allowed_origins=["*"],
)

app = agent_os.get_app()


# ============================================================
# ENDPOINT CUSTOM — Lista de creators disponiveis
# ============================================================
@app.get("/creators")
def listar_creators():
    """Retorna a lista de creators com nome e descricao do estilo."""
    profiles_dir = DB_DIR / "profiles"
    creators = []
    for autor in autores_disponiveis:
        descricao = ""
        perfil_path = profiles_dir / f"{autor}.json"
        if perfil_path.exists():
            import json as _j
            perfil = _j.loads(perfil_path.read_text(encoding="utf-8"))
            descricao = perfil.get("resumo_estilo", "")
        creators.append({"name": autor, "description": descricao})
    return creators


# CORS manual — o AgentOS seta allow_credentials=True que bloqueia "*"
from starlette.middleware.cors import CORSMiddleware

# Remove o CORS middleware do AgentOS (se existir) e adiciona o nosso
app.user_middleware = [m for m in app.user_middleware if m.cls is not CORSMiddleware]
app.middleware_stack = None  # forca rebuild
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.build_middleware_stack()


# ============================================================
# HEALTH CHECK — Render usa para monitorar o servico
# ============================================================
@app.get("/health")
def health_check():
    """Endpoint de health check para o Render."""
    return {
        "status": "ok",
        "model": "gpt-5-mini",
        "mode": "team",
        "agents": ["reels_copywriter", "stories_copywriter"],
        "creators": len(autores_disponiveis),
        "disk": "persistent" if RENDER_DISK else "local",
    }


# ============================================================
# STARTUP — Sincroniza dados em background (nao bloqueia a porta)
# ============================================================
import json as _json
import threading
from contextlib import asynccontextmanager


def _sincronizar_chromadb():
    """Sincroniza o ChromaDB em background (thread separada)."""
    print("\n=== BACKGROUND: Sincronizando ChromaDB ===\n")

    # 1) Transcricoes dos creators (JSONs em videos/*/)
    if VIDEOS_DIR.exists():
        for autor_dir in sorted(p for p in VIDEOS_DIR.iterdir() if p.is_dir()):
            autor = autor_dir.name
            for json_path in sorted(autor_dir.glob("*.json")):
                dados = _json.loads(json_path.read_text(encoding="utf-8"))
                texto = dados.get("transcricao", "")
                if texto.strip():
                    knowledge_base.add_content(
                        text_content=texto,
                        name=f"{autor} - {json_path.stem}",
                        metadata={
                            "tipo": "transcricao",
                            "autor": autor,
                            "arquivo": json_path.name,
                        },
                        skip_if_exists=True,
                    )
            print(f"  [transcricoes] {autor}: OK")

    # 2) Apostilas (PDFs)
    try:
        from ingest import ingerir_apostilas
        ingerir_apostilas()
        print(f"  [apostilas]: OK")
    except Exception as e:
        print(f"  [apostilas]: ERRO - {e}")

    # 3) YouTube — baixa transcricoes das URLs e ingere
    try:
        from youtube_ingest import main as ingerir_youtube
        ingerir_youtube()
        print(f"  [youtube]: OK")
    except Exception as e:
        print(f"  [youtube]: ERRO - {e}")

    # 4) Perfis de creators — gera a partir das transcricoes
    try:
        from profiles import main as gerar_perfis
        gerar_perfis()
        print(f"  [perfis]: OK")
    except Exception as e:
        print(f"  [perfis]: ERRO - {e}")

    print("\n=== BACKGROUND: ChromaDB pronto ===\n")


@asynccontextmanager
async def lifespan(application):
    """Inicia sincronizacao em background e libera a porta imediatamente."""
    thread = threading.Thread(target=_sincronizar_chromadb, daemon=True)
    thread.start()
    yield

app.router.lifespan_context = lifespan


# ============================================================
# INGESTAO — Processa videos, apostilas e YouTube antes de servir
# ============================================================

def ingerir_tudo():
    """Roda toda a pipeline de ingestao (videos, apostilas, YouTube, perfis)."""
    from transcribe import main as transcrever
    transcrever()

    from ingest import ingerir_apostilas
    ingerir_apostilas()

    from youtube_ingest import main as ingerir_youtube
    ingerir_youtube()

    # Gera perfis de estilo dos creators (so gera se nao existir)
    from profiles import main as gerar_perfis
    gerar_perfis()


if __name__ == "__main__":
    ingerir_tudo()
    agent_os.serve(app="agent:app", host="0.0.0.0", port=7777, reload=True)

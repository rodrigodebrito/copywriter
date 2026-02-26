# ============================================================
# agent.py — CopyWriter Agent
# ============================================================

from pathlib import Path
import os

from agno.agent import Agent
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
# Descobre quais autores existem na pasta videos/
autores_disponiveis = []
if VIDEOS_DIR.exists():
    autores_disponiveis = [p.name for p in VIDEOS_DIR.iterdir() if p.is_dir()]

lista_autores = ", ".join(autores_disponiveis) if autores_disponiveis else "Nenhum autor cadastrado ainda"

# ============================================================
# INSTRUCTIONS — Carrega o prompt do arquivo prompt.md
# ============================================================
# O prompt fica em arquivo separado para facilitar edicao
# sem precisar mexer no codigo Python.
PROMPT_FILE = BASE_DIR / "prompt.md"
prompt_base = PROMPT_FILE.read_text(encoding="utf-8")

# Injeta a lista de creators dinamicamente no final do prompt
INSTRUCTIONS = f"""{prompt_base}

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
# AGENT — Configuracao otimizada
# ============================================================
agent = Agent(
    # --- Identidade ---
    name="copywriter_master",
    description="CopyWriter Master — Cria roteiros e copies no estilo de creators especificos",
    instructions=INSTRUCTIONS,

    # --- Modelo ---
    model=OpenAIChat(
        id="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        reasoning_effort="medium",   # equilibrio entre velocidade e qualidade
        verbosity="high",            # respostas detalhadas (roteiros longos)
    ),
    # --- Streaming ---
    # Envia a resposta em tempo real para o AgentUI (sem travar esperando)
    stream=True,

    # --- Formatacao ---
    # Formata a resposta em Markdown para exibicao no AgentUI
    markdown=True,

    # --- Historico de conversas ---
    # Envia as ultimas 5 conversas como contexto (10 era demais, gastava tokens)
    db=storage,
    add_history_to_context=True,
    num_history_runs=5,

    # --- Memoria persistente ---
    # Salva e recupera memorias do usuario entre sessoes
    # (ex: preferencias, nomes, contextos recorrentes)
    update_memory_on_run=True,       # novo parametro (substitui enable_user_memories)
    add_memories_to_context=True,    # injeta memorias no prompt automaticamente

    # --- Knowledge Base (RAG) ---
    # Busca automatica no ChromaDB antes de responder
    knowledge=knowledge_base,
    search_knowledge=True,           # adiciona tool de busca no knowledge
    add_search_knowledge_instructions=True,  # instrui o modelo a buscar
    enable_agentic_knowledge_filters=True,   # agente pode filtrar por autor, tipo, etc.

    # --- Tools ---
    tools=tools if tools else None,
    tool_call_limit=10,              # previne loops infinitos de tool calls

    # --- Contexto extra ---
    add_datetime_to_context=True,    # agente sabe a data/hora atual
)

# ============================================================
# AGENT OS — Servidor web + API
# ============================================================
# CORS aberto para permitir chamadas de n8n, Loveable, etc.
# Em producao, restrinja para dominios especificos.
agent_os = AgentOS(
    id="copywriter",
    description="CopyWriter Master — Agente de roteiros e copies",
    agents=[agent],
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
        "creators": len(autores_disponiveis),
        "disk": "persistent" if RENDER_DISK else "local",
    }


# ============================================================
# STARTUP — Sempre sincroniza dados (incremental com skip_if_exists)
# ============================================================
# Roda toda vez no startup mas e rapido: skip_if_exists=True faz
# com que docs ja existentes sejam pulados instantaneamente.
# Assim, creators novos sao ingeridos automaticamente no deploy.

import json as _json
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application):
    """Sincroniza o ChromaDB no startup (incremental)."""
    print("\n=== STARTUP: Sincronizando ChromaDB ===\n")

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

    print("\n=== STARTUP: ChromaDB pronto ===\n")
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





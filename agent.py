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
# PATHS
# ============================================================
BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data"
APOSTILAS_DIR = BASE_DIR / "apostilas"
VIDEOS_DIR = BASE_DIR / "videos"

DB_DIR.mkdir(exist_ok=True)
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
        id="gpt-4.1-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
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
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
)

app = agent_os.get_app()


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





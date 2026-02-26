# CopyWriter Agent

Agente de IA que CLONA o estilo de criadores de conteudo (creators) para gerar roteiros e copies.

## Stack

- **Framework**: Agno v2.5.4 (orquestracao de agentes + Team mode)
- **LLM**: OpenAI GPT-5-mini (geracao) + Whisper (transcricao)
- **Vector DB**: ChromaDB (embeddings persistentes)
- **Embeddings**: OpenAI text-embedding-3-small
- **Memoria**: SQLite via agno.db.sqlite (historico + memorias de usuario)
- **Busca web**: Tavily (condicional — so se TAVILY_API_KEY existir)
- **YouTube**: youtube-transcript-api (transcricoes de videos do YouTube)
- **Server**: AgentOS + FastAPI (API + AgentUI)
- **Deploy**: Render (render.yaml com persistent disk)
- **Package manager**: uv

## Arquitetura Multi-Agente (Team Mode)

O sistema usa **Agno Team** com 3 componentes:

| Componente | Nome | Funcao |
|------------|------|--------|
| **Orquestrador** | `copywriter_master` | Team que recebe o usuario, pesquisa conteudo e delega |
| **Agente Reels** | `reels_copywriter` | Cria roteiros de video curto (30-60s) clonando estilo |
| **Agente Stories** | `stories_copywriter` | Cria sequencias de Stories interativos (Leandro Ladeira) |

**Modo**: `TeamMode.coordinate` — o orquestrador analisa o pedido e delega ao(s) especialista(s) adequado(s).

**Fluxo**:
1. Usuario envia tema → orquestrador pesquisa base
2. Usuario escolhe creator → orquestrador pergunta formato (Reels/Stories/Pacote)
3. Orquestrador delega ao(s) especialista(s)
4. Especialista(s) gera(m) conteudo no estilo do creator
5. Orquestrador entrega o resultado

## Arquivos principais

| Arquivo | Funcao |
|---------|--------|
| `agent.py` | Team + agentes (orquestrador, reels, stories), AgentOS, endpoints |
| `prompt.md` | Instrucoes do agente Reels (clonagem de estilo, fluxo, regras) |
| `stories_prompt.md` | Instrucoes do agente Stories (metodo Leandro Ladeira) |
| `transcribe.py` | Transcreve MP4 com Whisper → salva JSON → sobe pro ChromaDB |
| `ingest.py` | Ingere PDFs com metadados (pasta + classificacao LLM) → ChromaDB |
| `youtube_ingest.py` | Baixa transcricoes do YouTube → classifica → ChromaDB |
| `profiles.py` | Gera perfis de estilo (DNA de clonagem) dos creators → ChromaDB |
| `youtube_urls.txt` | URLs do YouTube para ingerir (uma por linha) |
| `render.yaml` | Configuracao de deploy no Render |
| `.env` | OPENAI_API_KEY, TAVILY_API_KEY |
| `pyproject.toml` | Dependencias do projeto |

## Estrutura de pastas

```
CopyWriter/
├── agent.py
├── prompt.md                # Prompt do agente Reels
├── stories_prompt.md        # Prompt do agente Stories
├── transcribe.py
├── ingest.py
├── youtube_ingest.py
├── profiles.py
├── youtube_urls.txt
├── .env
├── pyproject.toml
├── videos/                  # MP4s dos creators (cada subpasta = 1 creator)
│   ├── Fernando Freitas/
│   ├── Luiza Freitas/
│   └── Thamires Hauch/
├── apostilas/               # PDFs organizados por categoria/subcategoria
├── data/
│   ├── agent.db             # SQLite (sessoes + memorias)
│   ├── chromadb/            # Banco vetorial persistente
│   ├── profiles/            # Perfis de estilo dos creators (JSON)
│   └── youtube/             # Transcricoes do YouTube (JSON)
├── agent-ui/                # Frontend AgentUI (Next.js)
└── APOSTILA_COPYWRITER.html # Tutorial educativo do projeto
```

## Como rodar

```bash
# Instalar dependencias
uv sync

# Rodar o agente (transcreve videos + ingere PDFs + serve)
uv run agent.py

# AgentUI (frontend)
cd agent-ui && npm run dev
```

## Conceitos-chave

- **Clonagem de estilo**: Os agentes analisam 10 pontos (tom, energia, linguajar, bordoes, ritmo, analogias, emocao, hooks, CTA, estrutura) para replicar o creator
- **Perfis de creators**: DNA de estilo persistente — gerado uma vez, reutilizado em toda interacao (tipo="perfil")
- **Metadados por tipo**: `tipo="transcricao"` (estilo), `tipo="apostila"` (conteudo), `tipo="youtube"` (conteudo web), `tipo="perfil"` (DNA de clonagem)
- **Team coordinate**: Orquestrador decide quais agentes ativar, sintetiza respostas
- **Stories Leandro Ladeira**: Caixinhas de perguntas, enquetes, quizzes, interacao a cada 3 stories, sequencias de 7-12 stories
- **Startup automatico**: Ao rodar `uv run agent.py`, transcreve videos + ingere PDFs + ingere YouTube + gera perfis em background
- **Memoria persistente**: O agente memoriza correcoes do usuario ("ele nao fala assim") e melhora a clonagem ao longo do tempo

## Parametros do Team/Agent (tuning)

- `model="gpt-5-mini"` — modelo GPT-5 mini para todos os componentes
- `reasoning_effort="medium"` — equilibrio entre velocidade e qualidade
- `verbosity="low"` — respostas curtas e diretas
- `TeamMode.coordinate` — orquestrador delega seletivamente
- `stream=True` — resposta em tempo real
- `markdown=True` — formatacao na UI
- `num_history_runs=5` — ultimas 5 conversas como contexto
- `update_memory_on_run=True` — salva memorias automaticamente
- `search_knowledge=True` — busca no ChromaDB via tool
- `enable_agentic_knowledge_filters=True` — filtros por tipo, autor, etc.
- `tool_call_limit=10` — previne loops infinitos
- `add_datetime_to_context=True` — agente sabe a data atual

## Convencoes

- Prompts ficam em arquivos `.md` separados do codigo
- Lista de creators e injetada dinamicamente das pastas em `videos/`
- Transcricoes salvam em JSON (com metadados), nao TXT puro
- Toda ingestao usa `skip_if_exists=True` (incremental)
- Tavily e condicional — so ativa se a API key existir no .env
- Team usa `AgentOS(teams=[team])` em vez de `agents=[agent]`

## Conexao e Deploy

- **Local**: AgentOS sobe em `0.0.0.0:7777` com reload
- **AgentUI**: `http://localhost:3000` (frontend Next.js)
- **CORS**: liberado para `["*"]`
- **Render**: plano Starter com disco persistente em `/data` (1GB), 2 workers uvicorn
- **Disco persistente**: ChromaDB e SQLite salvam em `RENDER_DISK_PATH=/data` (sobrevive deploys)
- **Health check**: `GET /health`
- **API principal**: `POST /teams/copywriter_master/runs` (message, stream, session_id)
- **GitHub**: https://github.com/rodrigodebrito/copywriter

## Proximos Passos

### Fase 1 — Agente de Stories (multi-agente) ✅ CONCLUIDO
- Agente Reels + Agente Stories + Orquestrador Team
- Metodo Leandro Ladeira para Stories

### Fase 2 — Base de conhecimento Leandro Ladeira
Ingerir o curso/conteudo do Leandro Ladeira no RAG como fonte de conhecimento de copywriting

### Fase 3 — Multi-plataforma automatico
Um tema gera conteudo para TODAS as plataformas (Reels, YouTube, Carrossel, Caption, Stories, Twitter)

### Fase 4 — Calendario editorial
"Me gera o conteudo da semana" → calendario completo distribuido por dias

### Fase 5 — Evolucao tecnica
- PostgreSQL, Autenticacao JWT, ChromaDB Cloud, Detector de tendencias

# CopyWriter Agent

Agente de IA que CLONA o estilo de criadores de conteudo (creators) para gerar roteiros e copies.

## Stack

- **Framework**: Agno v2.5.4 (orquestracao de agentes)
- **LLM**: OpenAI GPT-4.1-mini (geracao) + Whisper (transcricao)
- **Vector DB**: ChromaDB (embeddings persistentes)
- **Embeddings**: OpenAI text-embedding-3-small
- **Memoria**: SQLite via agno.db.sqlite (historico + memorias de usuario)
- **Busca web**: Tavily (condicional — so se TAVILY_API_KEY existir)
- **YouTube**: youtube-transcript-api (transcricoes de videos do YouTube)
- **Server**: AgentOS + FastAPI (API + AgentUI)
- **Deploy**: Render (render.yaml com persistent disk)
- **Package manager**: uv

## Arquivos principais

| Arquivo | Funcao |
|---------|--------|
| `agent.py` | Configuracao do agente (model, tools, knowledge, storage, AgentOS) |
| `prompt.md` | Instrucoes do agente (comportamento, fluxo, regras de clonagem) |
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
├── prompt.md
├── transcribe.py
├── ingest.py
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

## Fluxo do agente

1. Usuario chega → agente pergunta o assunto
2. Usuario envia tema → agente pesquisa base (ChromaDB) + Tavily
3. Agente apresenta relatorio com pontos encontrados
4. Agente lista os creators disponiveis para o usuario escolher
5. Usuario escolhe → agente gera 10 hooks no estilo clonado
6. Usuario aprova → agente gera roteiro completo

Se o usuario envia TEXTO PRONTO (em vez de tema), o agente pula direto para perguntar o creator e reescreve o texto clonando o estilo.

## Conceitos-chave

- **Clonagem de estilo**: O agente analisa 10 pontos (tom, energia, linguajar, bordoes, ritmo, analogias, emocao, hooks, CTA, estrutura) para replicar o creator
- **Perfis de creators**: DNA de estilo persistente — gerado uma vez, reutilizado em toda interacao. Contem exemplos reais e regras praticas para clonar (tipo="perfil")
- **Metadados por tipo**: `tipo="transcricao"` (estilo), `tipo="apostila"` (conteudo), `tipo="youtube"` (conteudo web), `tipo="perfil"` (DNA de clonagem)
- **Startup automatico**: Ao rodar `uv run agent.py`, transcreve videos + ingere PDFs + ingere YouTube + gera perfis antes de servir (tudo incremental)
- **Memoria persistente**: O agente memoriza correcoes do usuario ("ele nao fala assim") e melhora a clonagem ao longo do tempo

## Parametros do Agent (tuning)

- `model="gpt-4.1-mini"`
- `stream=True` — resposta em tempo real
- `markdown=True` — formatacao na UI
- `num_history_runs=5` — ultimas 5 conversas como contexto
- `update_memory_on_run=True` — salva memorias automaticamente
- `search_knowledge=True` — busca no ChromaDB via tool
- `enable_agentic_knowledge_filters=True` — filtros dinamicos por tipo, autor, etc.
- `tool_call_limit=10` — previne loops infinitos
- `add_datetime_to_context=True` — agente sabe a data atual

## Convencoes

- Prompt fica em `prompt.md` separado do codigo (facilita edicao)
- Lista de creators e injetada dinamicamente das pastas em `videos/`
- Transcricoes salvam em JSON (com metadados), nao TXT puro
- Toda ingestao usa `skip_if_exists=True` (incremental)
- Tavily e condicional — so ativa se a API key existir no .env

## Conexao e Deploy

- **Local**: AgentOS sobe em `0.0.0.0:7777` com reload
- **AgentUI**: `http://localhost:3000` (frontend Next.js)
- **CORS**: liberado para localhost (local) e `["*"]` para deploy
- **Render**: `render.yaml` configurado com persistent disk em `/data`
- **API principal**: `POST /agents/copywriter_master/runs` (message, stream, session_id)
- **GitHub**: https://github.com/rodrigodebrito/copywriter

## Proximos Passos

### Fase 1 — Agente de Stories (multi-agente)
Criar um segundo agente especializado em **Stories com caixinha de perguntas/interacao**, complementando o Reels:
- **Agente Reels** (atual): gera roteiros de video curto
- **Agente Stories**: gera sequencia de stories com caixinhas, enquetes, perguntas, CTAs interativos — tudo conectado ao tema do Reels
- **Orquestrador (Team)**: usar o modo Team do Agno para coordenar os agentes — usuario pede conteudo, o orquestrador distribui para Reels + Stories automaticamente
- O usuario pede UM tema e recebe o pacote completo (roteiro + stories)

### Fase 2 — Base de conhecimento Leandro Ladeira
Ingerir o curso/conteudo do Leandro Ladeira no RAG como fonte de conhecimento de copywriting:
- Adicionar PDFs/transcricoes na pasta `apostilas/` com metadados apropriados
- O agente passa a usar as tecnicas do Ladeira como base para gerar copies mais persuasivas
- Complementa o conteudo tecnico das apostilas existentes

### Fase 3 — Multi-plataforma automatico
Um tema gera conteudo adaptado para TODAS as plataformas de uma vez:
- Reels/TikTok (roteiro curto 30-60s)
- YouTube (roteiro longo 5-10min)
- Carrossel Instagram (slides com copy)
- Caption/Legenda (texto persuasivo)
- Stories (sequencia de cards com interacao)
- Twitter/X (thread)
- Cada formato tem seu agente especializado no Team

### Fase 4 — Calendario editorial
"Me gera o conteudo da semana" → o orquestrador cria um calendario completo:
- Distribui temas pelos dias da semana
- Gera conteudo para cada plataforma
- Tudo no estilo do creator escolhido
- Exporta em formato organizado

### Fase 5 — Evolucao tecnica
- **PostgreSQL**: migrar de SQLite para Postgres no Render (escala)
- **Autenticacao**: JWT ou API key para proteger a API em producao
- **ChromaDB Cloud**: migrar de local para cloud (mais robusto)
- **Detector de tendencias**: Tavily puxa trending topics e sugere conteudos
- **Mais videos por creator**: expandir a base para perfis mais precisos



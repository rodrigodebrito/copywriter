# CopyWriter Agent

Agente de IA que CLONA o estilo de criadores de conteudo (creators) para gerar roteiros e copies.

## Stack

- **Framework**: Agno v2.5.4 (orquestracao de agentes)
- **LLM**: OpenAI GPT-4.1-mini (geracao) + Whisper (transcricao)
- **Vector DB**: ChromaDB (embeddings persistentes)
- **Embeddings**: OpenAI text-embedding-3-small
- **Memoria**: SQLite via agno.db.sqlite (historico + memorias de usuario)
- **Busca web**: Tavily (condicional — so se TAVILY_API_KEY existir)
- **Server**: AgentOS + FastAPI (API + AgentUI)
- **Package manager**: uv

## Arquivos principais

| Arquivo | Funcao |
|---------|--------|
| `agent.py` | Configuracao do agente (model, tools, knowledge, storage, AgentOS) |
| `prompt.md` | Instrucoes do agente (comportamento, fluxo, regras de clonagem) |
| `transcribe.py` | Transcreve MP4 com Whisper → salva JSON → sobe pro ChromaDB |
| `ingest.py` | Ingere PDFs com metadados (pasta + classificacao LLM) → ChromaDB |
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
│   └── chromadb/            # Banco vetorial persistente
├── agent-ui/                # Frontend AgentUI (Next.js)
└── APOSTILA_COPYWRITER.html # Tutorial educativo do projeto
```

## Como rodar

```bash
# Instalar dependencias
uv sync

# Rodar o agente (transcreve videos + ingere PDFs + serve)
python agent.py

# AgentUI (frontend)
cd agent-ui && npm run dev
```

## Fluxo do agente

1. Usuario chega → agente pergunta o assunto
2. Usuario envia tema → agente pesquisa base (ChromaDB) + Tavily
3. Agente apresenta relatorio com pontos encontrados
4. Agente RECOMENDA o creator mais relevante para o tema
5. Usuario escolhe → agente gera 10 hooks no estilo clonado
6. Usuario aprova → agente gera roteiro completo

Se o usuario envia TEXTO PRONTO (em vez de tema), o agente pula direto para perguntar o creator e reescreve o texto clonando o estilo.

## Conceitos-chave

- **Clonagem de estilo**: O agente analisa 10 pontos (tom, energia, linguajar, bordoes, ritmo, analogias, emocao, hooks, CTA, estrutura) para replicar o creator
- **Metadados**: Transcricoes tem `{tipo: "transcricao", autor: "..."}` (ESTILO). Apostilas tem `{tipo: "apostila", categoria: "...", tema: "..."}` (CONTEUDO)
- **Startup automatico**: Ao rodar `python agent.py`, transcreve videos novos e ingere PDFs novos antes de servir (tudo incremental com skip_if_exists)
- **Memoria persistente**: O agente memoriza correcoes do usuario ("ele nao fala assim") e melhora a clonagem ao longo do tempo

## Parametros do Agent (tuning)

- `stream=True` — resposta em tempo real
- `markdown=True` — formatacao na UI
- `num_history_runs=5` — ultimas 5 conversas como contexto
- `update_memory_on_run=True` — salva memorias automaticamente
- `search_knowledge=True` — busca no ChromaDB via tool
- `tool_call_limit=10` — previne loops infinitos
- `add_datetime_to_context=True` — agente sabe a data atual

## Convencoes

- Prompt fica em `prompt.md` separado do codigo (facilita edicao)
- Lista de creators e injetada dinamicamente das pastas em `videos/`
- Transcricoes salvam em JSON (com metadados), nao TXT puro
- Toda ingestao usa `skip_if_exists=True` (incremental)
- Tavily e condicional — so ativa se a API key existir no .env

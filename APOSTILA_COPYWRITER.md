# CopyWriter Agent — Apostila Completa para Iniciantes

---

## O que estamos construindo?

Um **agente de IA** que escreve roteiros e textos (copies) no estilo de autores
especificos. Voce da um tema, escolhe um autor, e o agente:

1. Procura nas **apostilas e transcricoes** que voce forneceu
2. Se nao encontrar, **busca na internet** automaticamente
3. Gera o conteudo no **estilo do autor** escolhido
4. **Lembra** das conversas anteriores entre sessoes

---

## Indice

1. [O que e um Agente de IA?](#1-o-que-e-um-agente-de-ia)
2. [Estrutura do Projeto](#2-estrutura-do-projeto)
3. [Variaveis de Ambiente (.env)](#3-variaveis-de-ambiente-env)
4. [Pathlib — Caminhos que funcionam em qualquer sistema](#4-pathlib--caminhos-que-funcionam-em-qualquer-sistema)
5. [SQLite — A Memoria do Agente](#5-sqlite--a-memoria-do-agente)
6. [Embeddings — Transformando texto em numeros](#6-embeddings--transformando-texto-em-numeros)
7. [ChromaDB — O Banco de Dados Vetorial](#7-chromadb--o-banco-de-dados-vetorial)
8. [Knowledge Base — A Base de Conhecimento](#8-knowledge-base--a-base-de-conhecimento)
9. [Chunking — Dividindo textos grandes](#9-chunking--dividindo-textos-grandes)
10. [Tavily — Busca na Internet](#10-tavily--busca-na-internet)
11. [Como tudo se conecta (RAG)](#11-como-tudo-se-conecta-rag)
12. [Dependencias do Projeto](#12-dependencias-do-projeto)
13. [Glossario](#13-glossario)

---

## 1. O que e um Agente de IA?

Pense num agente como um **assistente inteligente com ferramentas**.

Um chatbot normal (como o ChatGPT basico) so responde com base no que ele ja
aprendeu no treinamento. Um **agente** vai alem — ele pode:

- **Consultar documentos** seus (apostilas, transcricoes)
- **Buscar na internet** informacoes atualizadas
- **Lembrar** de conversas passadas
- **Tomar decisoes** sobre qual ferramenta usar

```
Chatbot normal:         Agente:

Pergunta → Resposta     Pergunta
                           ↓
                        Preciso de mais info?
                          /          \
                        Sim          Nao
                         ↓            ↓
                    Busca na      Responde
                    base/internet    direto
                         ↓
                      Responde
```

No nosso caso, usamos o framework **Agno** para construir o agente.
O Agno cuida de toda a "orquestracao" — ele decide quando buscar nos documentos,
quando usar o Tavily, e como montar a resposta final.

---

## 2. Estrutura do Projeto

```
CopyWriter/
│
├── agent.py              ← Configuracao do agente (o que voce esta estudando)
├── main.py               ← Ponto de entrada do programa
├── .env                  ← Chaves de API (NUNCA compartilhe este arquivo!)
├── pyproject.toml        ← Lista de dependencias do projeto
├── uv.lock               ← Versoes exatas das dependencias (gerado automaticamente)
│
├── data/                 ← Criada automaticamente pelo codigo
│   ├── agent.db          ← Banco SQLite (historico de conversas)
│   └── chromadb/         ← Banco vetorial (embeddings dos documentos)
│
├── apostilas/            ← Coloque seus PDFs aqui
│   ├── marketing.pdf
│   └── copywriting.pdf
│
└── videos/               ← Videos organizados por autor
    ├── Fernando Freitas/
    ├── Luiza Freitas/
    └── Thamires Hauch/
```

---

## 3. Variaveis de Ambiente (.env)

Chaves de API sao como **senhas** para acessar servicos externos.
Elas NUNCA devem ficar no codigo, por seguranca.

O arquivo `.env` fica assim:

```env
OPENAI_API_KEY=sk-proj-abc123...
TAVILY_API_KEY=tvly-abc123...
```

No codigo, usamos `load_dotenv()` para carregar essas variaveis:

```python
from dotenv import load_dotenv
load_dotenv()  # Le o arquivo .env e disponibiliza as variaveis
```

Depois disso, qualquer biblioteca que precise da `OPENAI_API_KEY` encontra
automaticamente — voce nao precisa passar manualmente.

**Por que nao colocar direto no codigo?**
- Se voce subir o codigo pro GitHub, qualquer pessoa ve sua chave
- Alguem pode usar sua chave e gerar custos na sua conta
- O `.gitignore` deve ignorar o `.env` para ele nunca ser commitado

---

## 4. Pathlib — Caminhos que funcionam em qualquer sistema

### O Problema

Windows usa `\` nos caminhos: `C:\Users\pasta\arquivo.txt`
Linux/Mac usam `/`: `/home/pasta/arquivo.txt`

Se voce escrever um caminho fixo como `/tmp/data.db`, **nao funciona no Windows**.

### A Solucao: pathlib

```python
from pathlib import Path

# Path(__file__) = caminho completo DESTE arquivo (agent.py)
# .parent = pasta onde o arquivo esta (raiz do projeto)
BASE_DIR = Path(__file__).parent

# O operador / junta caminhos de forma segura para qualquer SO
DB_DIR = BASE_DIR / "data"          # Windows: CopyWriter\data
                                     # Linux:   CopyWriter/data

APOSTILAS_DIR = BASE_DIR / "apostilas"
```

### Criando pastas automaticamente

```python
# mkdir() cria a pasta
# exist_ok=True = nao da erro se a pasta ja existir
DB_DIR.mkdir(exist_ok=True)
APOSTILAS_DIR.mkdir(exist_ok=True)
```

Assim, na primeira vez que rodar o projeto, as pastas sao criadas sozinhas.

---

## 5. SQLite — A Memoria do Agente

### O que e SQLite?

SQLite e um **banco de dados que fica em um unico arquivo** no seu computador.
Nao precisa instalar servidor, nao precisa de configuracao. E como um Excel,
mas para programas.

### Para que usamos?

Para guardar o **historico de conversas**. Quando voce fecha o programa e abre
de novo, o agente lembra do que voces conversaram.

```python
from agno.db.sqlite import SqliteDb

storage = SqliteDb(
    db_file=str(DB_DIR / "agent.db"),  # Arquivo: data/agent.db
)
```

### Como funciona na pratica?

```
Sessao 1:
  Voce: "Escreva um roteiro sobre marketing digital"
  Agente: "Aqui esta o roteiro..."
  → Salva no SQLite

Sessao 2 (outro dia):
  Voce: "Melhore o roteiro que fizemos ontem"
  Agente: (consulta o SQLite) "Encontrei nosso roteiro anterior. Aqui esta melhorado..."
```

Sem o SQLite, o agente "esqueceria" tudo quando voce fechasse o programa.

---

## 6. Embeddings — Transformando texto em numeros

Este e o conceito **mais importante** para entender o projeto.

### O Problema

Computadores nao entendem texto. Eles entendem numeros.
Se voce quer buscar "dicas de copywriting" nos seus PDFs, uma busca por
palavras exatas ("ctrl+F") so encontra se o texto tiver exatamente essas palavras.

Mas e se o PDF falar sobre "tecnicas de escrita persuasiva"?
E a **mesma coisa**, mas com palavras diferentes!

### A Solucao: Embeddings

Um **embedding** transforma texto em uma lista de numeros (vetor) que
representa o **significado** do texto.

```
"dicas de copywriting"      → [0.12, -0.45, 0.78, 0.33, ...]
"tecnicas de escrita"       → [0.11, -0.43, 0.76, 0.35, ...]  ← SIMILAR!
"receita de bolo"           → [-0.89, 0.22, -0.15, 0.67, ...]  ← DIFERENTE!
```

Textos com significado parecido geram numeros parecidos.
Textos com significado diferente geram numeros diferentes.

### No nosso codigo

```python
from agno.knowledge.embedder.openai import OpenAIEmbedder

# Usamos o modelo text-embedding-3-small da OpenAI
# Ele e rapido, barato, e gera vetores com 1536 dimensoes
embedder = OpenAIEmbedder(id="text-embedding-3-small")
```

Cada vez que um PDF e carregado, o texto e enviado para a OpenAI,
que retorna os embeddings. Esses embeddings sao salvos no ChromaDB.

**Custo:** text-embedding-3-small custa ~$0.02 por 1 milhao de tokens
(muito barato — um PDF inteiro custa centavos).

---

## 7. ChromaDB — O Banco de Dados Vetorial

### O que e um banco vetorial?

Um banco de dados normal (como SQLite) busca por valores exatos:
"me de todos os registros onde nome = 'Joao'"

Um banco **vetorial** busca por **similaridade**:
"me de os textos mais parecidos com 'dicas de marketing'"

### Como funciona?

```
1. Voce carrega um PDF sobre copywriting
2. O texto e dividido em pedacos (chunks)
3. Cada pedaco e transformado em embedding (numeros)
4. Os embeddings sao salvos no ChromaDB

Depois, quando voce pergunta algo:

1. Sua pergunta e transformada em embedding
2. O ChromaDB compara com todos os embeddings salvos
3. Retorna os pedacos de texto mais SIMILARES
```

### No nosso codigo

```python
from agno.vectordb.chroma import ChromaDb

vector_db = ChromaDb(
    collection="apostilas",                        # Nome da colecao (como uma tabela)
    path=str(DB_DIR / "chromadb"),                 # Onde salvar no disco
    embedder=OpenAIEmbedder(id="text-embedding-3-small"),  # Modelo de embedding
    persistent_client=True,                        # Manter dados entre execucoes
)
```

### Analogia simples

Imagine uma **biblioteca**.

- **Banco normal (SQLite):** Voce pede "livro numero 42" e o bibliotecario
  busca pelo numero exato.
- **Banco vetorial (ChromaDB):** Voce diz "quero algo sobre como vender mais"
  e o bibliotecario traz os livros mais relevantes, mesmo que nenhum tenha
  exatamente essas palavras no titulo.

---

## 8. Knowledge Base — A Base de Conhecimento

A Knowledge Base e o componente que **conecta tudo**: le os PDFs, divide em
pedacos, transforma em embeddings, e salva no ChromaDB.

```python
from agno.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader

knowledge_base = Knowledge(
    vector_db=vector_db,                    # Onde salvar os embeddings
    readers={                               # Quais tipos de arquivo sabe ler
        "pdf": PDFReader(                   # Leitor de PDFs
            chunking_strategy=SemanticChunking()  # Como dividir o texto
        )
    },
)
```

### Fluxo completo

```
apostilas/marketing.pdf
        ↓
    PDFReader (extrai o texto do PDF)
        ↓
    SemanticChunking (divide em pedacos por significado)
        ↓
    OpenAIEmbedder (transforma cada pedaco em numeros)
        ↓
    ChromaDB (salva os embeddings no disco)
```

### O parametro `readers`

O `readers` e um **dicionario** (dict), nao uma lista.
A chave e o nome do tipo de documento, o valor e o leitor:

```python
readers={
    "pdf": PDFReader(...),      # Le arquivos PDF
    # No futuro podemos adicionar:
    # "txt": TextReader(...),   # Le arquivos TXT
    # "csv": CSVReader(...),    # Le arquivos CSV
}
```

---

## 9. Chunking — Dividindo textos grandes

### Por que dividir?

Modelos de IA tem um limite de texto que podem processar por vez (contexto).
Um PDF de 100 paginas nao cabe inteiro. Alem disso, se voce manda o PDF inteiro,
a IA se perde — e melhor mandar so os trechos relevantes.

### Tipos de Chunking

```
Chunking por tamanho fixo (ruim):
┌──────────────────────────┐
│ "O marketing digital e   │  ← Pedaco 1 (500 caracteres)
│ fundamental para..."      │
├──────────────────────────┤
│ "...empresas modernas.   │  ← Pedaco 2 (500 caracteres)
│ A principal vantagem"     │     Cortou no meio da ideia!
├──────────────────────────┤
│ " e o alcance global..." │  ← Pedaco 3
└──────────────────────────┘

Chunking semantico (bom):
┌──────────────────────────┐
│ "O marketing digital e   │  ← Pedaco 1 (ideia completa)
│ fundamental para          │
│ empresas modernas."       │
├──────────────────────────┤
│ "A principal vantagem    │  ← Pedaco 2 (ideia completa)
│ e o alcance global que   │
│ permite atingir clientes │
│ em qualquer lugar."       │
└──────────────────────────┘
```

O **SemanticChunking** usa IA para identificar onde uma ideia termina e outra
comeca, mantendo cada pedaco coerente.

```python
from agno.knowledge.chunking.semantic import SemanticChunking

# O SemanticChunking usa a biblioteca "chonkie" por baixo dos panos
chunking = SemanticChunking()
```

---

## 10. Tavily — Busca na Internet

O Tavily e uma **API de busca na internet** feita especialmente para agentes de IA.
Diferente do Google, ele retorna texto limpo e organizado, pronto para a IA usar.

### Para que usamos?

Quando o usuario pede um conteudo sobre um tema que **nao esta nas apostilas**,
o agente usa o Tavily para buscar informacoes atualizadas na internet.

```python
from agno.tools.tavily import TavilyTools

# O agente recebe o Tavily como "ferramenta"
# Ele decide sozinho quando usar (quando nao encontra na base)
tools = [TavilyTools()]
```

### Fluxo de decisao

```
Usuario: "Escreva sobre tendencias de marketing 2026"
                    ↓
        Busca no ChromaDB...
                    ↓
        Encontrou conteudo relevante?
              /           \
           Sim             Nao
            ↓               ↓
    Usa o conteudo      Busca no Tavily
    das apostilas       (internet)
            \              /
             ↓            ↓
         Gera o roteiro combinando
         as informacoes + estilo do autor
```

---

## 11. Como tudo se conecta (RAG)

O padrao que estamos usando se chama **RAG** — Retrieval Augmented Generation.
Em portugues: "Geracao Aumentada por Recuperacao".

### Sem RAG (chatbot comum)

```
Pergunta → LLM → Resposta (baseada so no treinamento)
```

O problema: a IA pode "inventar" coisas (alucinar) e nao conhece seus documentos.

### Com RAG (nosso agente)

```
Pergunta
   ↓
Busca documentos relevantes (ChromaDB)  ← RECUPERACAO
   ↓
Envia: pergunta + documentos encontrados → LLM  ← AUMENTO
   ↓
Resposta baseada nos SEUS documentos  ← GERACAO
```

### O fluxo completo do CopyWriter

```
┌─────────────────────────────────────────────────────────────┐
│                     COPYWRITER AGENT                        │
│                                                             │
│  1. Usuario pede: "Roteiro sobre X no estilo do autor Y"    │
│                          ↓                                  │
│  2. Busca no ChromaDB:                                      │
│     - Trechos de apostilas sobre o tema X                   │
│     - Transcricoes do autor Y (para captar o estilo)        │
│                          ↓                                  │
│  3. Encontrou o suficiente?                                 │
│        Sim → usa o conteudo encontrado                      │
│        Nao → complementa com Tavily (internet)              │
│                          ↓                                  │
│  4. Monta o prompt:                                         │
│     "Com base nestes documentos [docs], escreva um          │
│      roteiro sobre [tema] no estilo de [autor]"             │
│                          ↓                                  │
│  5. OpenAI gera o roteiro                                   │
│                          ↓                                  │
│  6. Salva a conversa no SQLite (memoria)                    │
│                          ↓                                  │
│  7. Retorna o roteiro para o usuario                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Dependencias do Projeto

Cada biblioteca no `pyproject.toml` tem uma funcao especifica:

| Pacote | Para que serve |
|--------|---------------|
| `agno` | Framework principal do agente — orquestra tudo |
| `openai` | Comunicacao com a API da OpenAI (GPT + Embeddings) |
| `chromadb` | Banco de dados vetorial (armazena embeddings) |
| `pypdf` | Leitura de arquivos PDF |
| `chonkie[semantic]` | Divisao inteligente de texto (semantic chunking) |
| `sqlalchemy` | Biblioteca que o agno usa para acessar o SQLite |
| `python-dotenv` | Carrega variaveis de ambiente do arquivo .env |
| `tavily` | API de busca na internet para agentes de IA |

### O que e `uv`?

`uv` e o **gerenciador de pacotes** que usamos (alternativa ao pip).
Ele e muito mais rapido que o pip e gerencia ambientes virtuais automaticamente.

Comandos uteis:
```bash
uv pip install pacote        # Instala um pacote
uv pip install --upgrade pacote  # Atualiza um pacote
uv pip list                  # Lista pacotes instalados
uv sync                     # Instala tudo do pyproject.toml
```

---

## 13. Glossario

| Termo | Significado |
|-------|------------|
| **Agente** | Programa de IA que usa ferramentas para completar tarefas |
| **LLM** | Large Language Model — modelo grande de linguagem (ex: GPT-4) |
| **Embedding** | Representacao numerica (vetor) do significado de um texto |
| **Vector DB** | Banco de dados que busca por similaridade de significado |
| **RAG** | Retrieval Augmented Generation — padrao de buscar docs antes de gerar texto |
| **Chunk** | Pedaco de texto resultante da divisao de um documento maior |
| **Token** | Unidade de texto para a IA (~4 caracteres ou ~0.75 palavras) |
| **API** | Interface para comunicacao entre programas |
| **API Key** | Chave/senha para acessar uma API |
| **Framework** | Conjunto de ferramentas e padroes para construir software |
| **.env** | Arquivo que guarda variaveis de ambiente (chaves, configs) |
| **venv** | Ambiente virtual — instalacao isolada de pacotes Python |
| **Prompt** | Instrucao/pergunta enviada para a IA |
| **Alucinacao** | Quando a IA inventa informacoes que parecem verdadeiras mas nao sao |
| **Contexto** | Quantidade de texto que a IA consegue processar de uma vez |
| **Persistente** | Que sobrevive apos fechar o programa (salvo em disco) |

---

## Proximos Passos

O que falta implementar:

1. **Transcricao de videos** — Extrair audio e transcrever com Whisper
2. **Instanciar o Agent** — Conectar todos os componentes (storage, knowledge, tools)
3. **Interface** — Como o usuario vai interagir (terminal, web, etc.)
4. **Prompt do sistema** — Instrucoes para o agente sobre como escrever roteiros

---

*Apostila gerada para o projeto CopyWriter*
*Ultima atualizacao: Fevereiro 2026*

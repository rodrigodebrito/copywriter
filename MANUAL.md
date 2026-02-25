# Manual de Operacoes — CopyWriter Agent

## 1. Adicionar Novo Creator

### Passo 1 — Criar a pasta
Crie uma pasta com o nome do creator dentro de `videos/`:
```
videos/Nome do Creator/
```

### Passo 2 — Colocar os videos
Copie os MP4 dos videos do creator para a pasta criada.

### Passo 3 — Transcrever
```bash
uv run python transcribe.py
```
Transcreve os MP4 com Whisper, salva JSONs e ingere no ChromaDB.

### Passo 4 — Gerar perfil de estilo
```bash
uv run python profiles.py
```
Analisa todas as transcricoes e gera o "DNA de clonagem" do creator.

### Passo 5 — Commitar e subir pro Render
```bash
git add "videos/Nome do Creator/"
git commit -m "feat: adicionar creator Nome do Creator"
git push
```
O Render faz auto-deploy. Os MP4 nao vao pro git (so os JSONs).

---

## 2. Adicionar Videos do YouTube

### Passo 1 — Editar o arquivo de URLs
Abra `youtube_urls.txt` e adicione as URLs (uma por linha):
```
# Comentarios com #
https://www.youtube.com/watch?v=XXXXX
https://youtu.be/YYYYY
```

### Passo 2 — Processar
```bash
uv run python youtube_ingest.py
```
Baixa as transcricoes, classifica o tema e ingere no ChromaDB.

### Passo 3 — Commitar e subir pro Render
```bash
git add youtube_urls.txt
git commit -m "feat: adicionar videos YouTube"
git push
```

---

## 3. Adicionar Apostilas (PDFs)

### Passo 1 — Colocar os PDFs
Copie os PDFs para a pasta `apostilas/`, organizados por categoria:
```
apostilas/
├── narcisismo/
│   └── manual_narcisismo.pdf
├── autoestima/
│   └── guia_autoestima.pdf
```

### Passo 2 — Processar
```bash
uv run python ingest.py
```
Le os PDFs, classifica com GPT e ingere no ChromaDB com metadados.

### Passo 3 — Commitar
Os PDFs estao no `.gitignore` (sao pesados). A ingestao e so local.
Para o Render ter acesso, seria necessario migrar para o plano Starter com disco persistente.

---

## 4. Regenerar Perfis (quando adicionar mais videos de um creator)

Se voce adicionou MAIS videos de um creator que ja existe:

### Passo 1 — Transcrever os novos videos
```bash
uv run python transcribe.py
```

### Passo 2 — Regenerar o perfil (com --force)
```bash
uv run python profiles.py --force
```
O `--force` regenera o perfil mesmo se ja existe, incluindo os novos videos na analise.

### Passo 3 — Commitar e subir
```bash
git add "videos/Nome do Creator/"
git commit -m "feat: novos videos de Nome do Creator"
git push
```

---

## 5. Rodar Tudo de Uma Vez (local)

Para transcrever + ingerir PDFs + YouTube + gerar perfis + servir:
```bash
uv run python agent.py
```
Isso roda `ingerir_tudo()` e depois sobe o servidor em `localhost:7777`.

---

## 6. Testar Local

### Servidor
```bash
uv run python agent.py
```
Acesse: http://localhost:7777

### Frontend (AgentUI)
```bash
cd agent-ui && npm run dev
```
Acesse: http://localhost:3000

---

## Resumo Rapido de Comandos

| Acao | Comando |
|------|---------|
| Transcrever videos | `uv run python transcribe.py` |
| Ingerir PDFs | `uv run python ingest.py` |
| Ingerir YouTube | `uv run python youtube_ingest.py` |
| Gerar perfis | `uv run python profiles.py` |
| Regenerar perfis | `uv run python profiles.py --force` |
| Rodar tudo + servidor | `uv run python agent.py` |
| Commitar | `git add . && git commit -m "mensagem" && git push` |

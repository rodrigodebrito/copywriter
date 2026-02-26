# ============================================================
# transcribe.py — Transcreve videos e salva no Knowledge Base
# ============================================================
# Percorre as pastas de autores em videos/, transcreve cada MP4
# usando Whisper da OpenAI, salva as transcricoes em JSON
# (com metadados) e sobe pro ChromaDB.
#
# Formato JSON de saida:
# {
#   "autor": "Fernando Freitas",
#   "tipo": "transcricao",
#   "arquivo_original": "video.mp4",
#   "transcricao": "texto transcrito..."
# }
#
# Uso:
#   python transcribe.py
# ============================================================

import json
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from agent import knowledge_base, VIDEOS_DIR, DB_DIR

load_dotenv()


def _extrair_audio(caminho_video: Path) -> Path:
    """
    Extrai o audio de um video MP4 para MP3 comprimido usando ffmpeg.
    Retorna o caminho do arquivo MP3 temporario.
    Um video de 100MB vira ~3-5MB de audio.
    """
    audio_path = Path(tempfile.mktemp(suffix=".mp3"))
    subprocess.run(
        [
            "ffmpeg", "-i", str(caminho_video),
            "-vn",              # sem video
            "-acodec", "libmp3lame",
            "-ab", "64k",       # bitrate baixo (suficiente pra voz)
            "-ar", "16000",     # sample rate 16kHz (ideal pro Whisper)
            "-ac", "1",         # mono
            "-y",               # sobrescreve se existir
            str(audio_path),
        ],
        capture_output=True,
        check=True,
    )
    return audio_path


def transcrever_video(caminho_video: Path) -> str:
    """
    Transcreve um arquivo de video usando Whisper da OpenAI.
    Se o arquivo for maior que 24MB, extrai o audio primeiro com ffmpeg.
    """
    client = OpenAI()
    tamanho_mb = caminho_video.stat().st_size / (1024 * 1024)

    arquivo_enviar = caminho_video
    audio_temp = None

    if tamanho_mb > 24:
        print(f"  Arquivo grande ({tamanho_mb:.1f}MB) — extraindo audio...")
        try:
            audio_temp = _extrair_audio(caminho_video)
            tamanho_audio = audio_temp.stat().st_size / (1024 * 1024)
            print(f"  Audio extraido: {tamanho_audio:.1f}MB")
            arquivo_enviar = audio_temp
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  AVISO: ffmpeg nao disponivel ({e}), enviando MP4 direto...")

    print(f"  Transcrevendo com Whisper...")
    try:
        with open(arquivo_enviar, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="pt",
            )
        return transcription.text
    finally:
        if audio_temp and audio_temp.exists():
            audio_temp.unlink()


def salvar_transcricao(texto: str, autor: str, nome_arquivo: str):
    """
    Salva a transcricao como arquivo .json na pasta do autor
    (com metadados: autor, tipo, arquivo_original)
    e adiciona ao knowledge base do ChromaDB.
    """
    pasta_autor = VIDEOS_DIR / autor
    stem = Path(nome_arquivo).stem

    # ---- Salva em JSON com metadados ----
    json_path = pasta_autor / f"{stem}.json"
    dados = {
        "autor": autor,
        "tipo": "transcricao",
        "arquivo_original": nome_arquivo,
        "transcricao": texto,
    }
    json_path.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Salvo em: {json_path.name}")

    # ---- Adiciona ao ChromaDB com metadata ----
    metadata = {
        "tipo": "transcricao",
        "autor": autor,
        "arquivo": json_path.name,
    }

    print(f"  Adicionando ao ChromaDB...")
    knowledge_base.add_content(
        text_content=texto,
        name=f"{autor} - {stem}",
        metadata=metadata,
        skip_if_exists=True,
    )


def converter_txt_para_json(txt_path: Path, autor: str):
    """
    Converte um .txt existente para .json com metadados.
    Util para migrar transcricoes antigas que foram salvas em .txt.
    """
    texto = txt_path.read_text(encoding="utf-8")
    if not texto.strip():
        return None

    stem = txt_path.stem
    json_path = txt_path.parent / f"{stem}.json"

    dados = {
        "autor": autor,
        "tipo": "transcricao",
        "arquivo_original": f"{stem}.mp4",
        "transcricao": texto,
    }
    json_path.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Convertido {txt_path.name} -> {json_path.name}")
    return texto


def main():
    print("=" * 50)
    print("  CopyWriter — Transcricao de Videos")
    print("=" * 50)
    print()

    if not VIDEOS_DIR.exists():
        print("Pasta videos/ nao encontrada!")
        return

    # Percorre cada pasta de autor
    autores = [p for p in VIDEOS_DIR.iterdir() if p.is_dir()]

    if not autores:
        print("Nenhuma pasta de autor encontrada em videos/")
        return

    total_videos = 0
    total_transcritos = 0

    for pasta_autor in sorted(autores):
        autor = pasta_autor.name
        videos = list(pasta_autor.glob("*.mp4"))

        if not videos:
            print(f"[{autor}] Nenhum video encontrado")
            continue

        print(f"\n--- {autor} ({len(videos)} videos) ---\n")

        for i, video_path in enumerate(sorted(videos), 1):
            total_videos += 1
            nome = video_path.name
            stem = video_path.stem

            # Verifica se ja foi transcrito (.json ou .txt existente)
            json_path = pasta_autor / f"{stem}.json"
            txt_path = pasta_autor / f"{stem}.txt"

            if json_path.exists():
                # Ja tem JSON — so garante que esta no ChromaDB
                print(f"[{i}/{len(videos)}] {nome} — ja transcrito (JSON), pulando")
                dados = json.loads(json_path.read_text(encoding="utf-8"))
                texto = dados.get("transcricao", "")
                if texto.strip():
                    metadata = {
                        "tipo": "transcricao",
                        "autor": autor,
                        "arquivo": json_path.name,
                    }
                    knowledge_base.add_content(
                        text_content=texto,
                        name=f"{autor} - {stem}",
                        metadata=metadata,
                        skip_if_exists=True,
                    )
                total_transcritos += 1
                continue

            if txt_path.exists():
                # Tem .txt mas nao .json — converte para JSON
                print(f"[{i}/{len(videos)}] {nome} — convertendo TXT para JSON")
                texto = converter_txt_para_json(txt_path, autor)
                if texto and texto.strip():
                    metadata = {
                        "tipo": "transcricao",
                        "autor": autor,
                        "arquivo": f"{stem}.json",
                    }
                    knowledge_base.add_content(
                        text_content=texto,
                        name=f"{autor} - {stem}",
                        metadata=metadata,
                        skip_if_exists=True,
                    )
                total_transcritos += 1
                continue

            # Nenhuma transcricao existe — transcrever
            print(f"[{i}/{len(videos)}] {nome}")

            try:
                texto = transcrever_video(video_path)
                salvar_transcricao(texto, autor, nome)
                total_transcritos += 1
                print(f"  OK!")
            except Exception as e:
                print(f"  ERRO: {e}")

    print(f"\n{'=' * 50}")
    print(f"  Concluido: {total_transcritos}/{total_videos} videos transcritos")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

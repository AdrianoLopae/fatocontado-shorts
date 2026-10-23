"""Posta no Instagram (@fatocontadobrasil) o Short da fila cujo horário já chegou.

Roda no GitHub Actions nos mesmos horários do YouTube. Fila: fila/NNNN.json + fila/NNNN.mp4
(o PC manda pra cá). Depois de postar, tira da fila e registra em postados.json.
"""
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import os

import requests

RAIZ = Path(__file__).resolve().parents[2]
FILA = RAIZ / "fila"
POSTADOS = RAIZ / "postados.json"
SITE = "https://adrianolopae.github.io/fatocontado-shorts"


def main():
    if not os.environ.get("IG_TOKEN"):
        print("sem token do Instagram ainda (segredo IG_TOKEN): nada a fazer")
        return
    import ig
    agora = datetime.now(timezone.utc)
    prontos = []
    for a in sorted(FILA.glob("*.json")):
        d = json.loads(a.read_text(encoding="utf-8"))
        quando = datetime.fromisoformat(d["publicar_em"])
        # janela: do horário marcado até 3 h depois (atraso do Actions); mais velho que isso fica para revisão
        if quando <= agora + timedelta(minutes=10) and agora - quando < timedelta(hours=3):
            prontos.append((quando, a, d))
    if not prontos:
        print("nada no horário agora")
        return
    quando, arq, d = sorted(prontos)[0]
    url = f"{SITE}/fila/{arq.stem}.mp4"
    for _ in range(30):
        if requests.head(url, timeout=20).status_code == 200:
            break
        time.sleep(10)
    print(f"postando: {d['titulo']}")
    ig_id = ig.publicar_reel(url, d["legenda"])
    postados = json.loads(POSTADOS.read_text(encoding="utf-8")) if POSTADOS.exists() else []
    postados.append({"titulo": d["titulo"], "youtube_id": d.get("youtube_id"), "ig_id": ig_id,
                     "postado": agora.isoformat(timespec="seconds")})
    POSTADOS.write_text(json.dumps(postados, ensure_ascii=False, indent=1), encoding="utf-8")
    arq.unlink()
    (FILA / f"{arq.stem}.mp4").unlink(missing_ok=True)
    git = lambda *a: subprocess.run(["git", "-C", str(RAIZ), *a], check=True)
    git("config", "user.name", "robo-fatocontado")
    git("config", "user.email", "robo@users.noreply.github.com")
    git("add", "-A")
    git("commit", "-m", f"postado: {d['titulo'][:50]}")
    git("push")
    print(f"publicado no Instagram: {ig_id}")


if __name__ == "__main__":
    main()

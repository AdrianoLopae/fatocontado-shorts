"""Posta no Instagram (@fatocontadobrasil) e na página do Facebook o Short da fila cujo horário chegou.

Roda no GitHub Actions nos mesmos horários do YouTube. Fila: fila/NNNN.json + fila/NNNN.mp4
(o PC manda pra cá). Cada rede só posta se o segredo dela existir (IG_TOKEN / FB_PAGE_TOKEN).
Guarda o id de cada rede no json para nunca postar duas vezes; sai da fila quando todas as redes ligadas postaram.
"""
import json
import os
import subprocess
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
FILA = RAIZ / "fila"
POSTADOS = RAIZ / "postados.json"
SITE = "https://adrianolopae.github.io/fatocontado-shorts"


def redes():
    r = {}
    if os.environ.get("IG_TOKEN"):
        import ig
        r["ig"] = ig.publicar_reel
    if os.environ.get("FB_PAGE_TOKEN"):
        import fb
        r["fb"] = fb.publicar_reel
    return r


def main():
    ligadas = redes()
    if not ligadas:
        print("nenhuma rede ligada ainda (segredos IG_TOKEN / FB_PAGE_TOKEN): nada a fazer")
        return
    agora = datetime.now(timezone.utc)
    prontos = []
    for a in sorted(FILA.glob("*.json")):
        d = json.loads(a.read_text(encoding="utf-8"))
        quando = datetime.fromisoformat(d["publicar_em"])
        # janela: do horário marcado até 3 h depois (atraso do Actions)
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
    erro = False
    for rede, publicar in ligadas.items():
        if d.get(f"{rede}_id"):
            continue
        try:
            print(f"{rede}: postando {d['titulo']}")
            d[f"{rede}_id"] = publicar(url, d["legenda"])
            print(f"{rede}: publicado {d[f'{rede}_id']}")
        except Exception:
            erro = True
            print(f"{rede}: ERRO\n{traceback.format_exc()}")
    if all(d.get(f"{r}_id") for r in ligadas):
        postados = json.loads(POSTADOS.read_text(encoding="utf-8")) if POSTADOS.exists() else []
        postados.append({k: d.get(k) for k in ("titulo", "youtube_id", "ig_id", "fb_id")} |
                        {"postado": agora.isoformat(timespec="seconds")})
        POSTADOS.write_text(json.dumps(postados, ensure_ascii=False, indent=1), encoding="utf-8")
        arq.unlink()
        (FILA / f"{arq.stem}.mp4").unlink(missing_ok=True)
    else:
        arq.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    git = lambda *a: subprocess.run(["git", "-C", str(RAIZ), *a], check=True)
    git("config", "user.name", "robo-fatocontado")
    git("config", "user.email", "robo@users.noreply.github.com")
    git("add", "-A")
    if subprocess.run(["git", "-C", str(RAIZ), "diff", "--cached", "--quiet"]).returncode:
        git("commit", "-m", f"postado: {d['titulo'][:50]}")
        git("push")
    if erro:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Posta no Instagram (@fatocontadobrasil), na página do Facebook e no TikTok (@fatocontadobrasil) o Short da fila cujo horário chegou.

Roda no GitHub Actions nos mesmos horários do YouTube. Fila: fila/NNNN.json + fila/NNNN.mp4
(o PC manda pra cá). Cada rede só posta se o segredo dela existir (IG_TOKEN / FB_PAGE_TOKEN / TT_REFRESH_TOKEN).
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
    # Instagram desligado enquanto existir o arquivo "instagram_desligado" na raiz do repo
    if os.environ.get("IG_TOKEN") and not (RAIZ / "instagram_desligado").exists():
        import ig
        r["ig"] = ig.publicar_reel
    if os.environ.get("FB_PAGE_TOKEN"):
        import fb
        r["fb"] = fb.publicar_reel
    if os.environ.get("NC_PAGE_TOKEN"):     # página New Clipador (13/11/2026): só itens com "nc" em "redes"
        import fb
        r["nc"] = fb.na_pagina(os.environ["NC_PAGE_TOKEN"], os.environ["NC_PAGE_ID"])
    if os.environ.get("TT_REFRESH_TOKEN") and os.environ.get("TT_CLIENT_KEY"):
        import tt
        r["tt"] = tt.publicar_video
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
    erro = False
    for quando, arq, d in sorted(prontos):     # posta TODOS os itens do horário (ex.: 17h no fb e no ig)
        url = f"{SITE}/fila/{arq.stem}.mp4"
        for _ in range(30):
            if requests.head(url, timeout=20).status_code == 200:
                break
            time.sleep(10)
        for rede, publicar in ligadas.items():
            if d.get(f"{rede}_id"):
                continue
            if rede == "nc" and "nc" not in (d.get("redes") or []):   # New Clipador só recebe o que é dele
                d["nc_id"] = "pulado: outra página"
                continue
            if d.get("redes") and rede not in d["redes"]:       # item só para algumas redes (ex.: longo vertical só no fb)
                d[f"{rede}_id"] = "pulado: outra rede"
                continue
            if rede == "ig" and (d.get("duracao") or 0) > 175:   # Instagram só recebe o Reels (curto vertical)
                d["ig_id"] = "pulado: longo"
                continue
            if rede == "tt" and not 61 <= (d.get("duracao") or 0) <= 178:   # TikTok: só de 1 a 3 min (monetização)
                d["tt_id"] = "pulado: fora de 1 a 3 min"
                continue
            try:
                print(f"{rede}: postando {d['titulo']}")
                if rede in ("fb", "nc"):
                    th = f"{SITE}/fila/{arq.stem}.jpg" if d.get("thumb") else None
                    d[f"{rede}_id"] = publicar(url, d["legenda"], d["titulo"], d.get("duracao") or 0, th)
                elif rede == "tt":
                    d["tt_id"] = publicar(FILA / f"{arq.stem}.mp4", d["legenda"])
                else:
                    d[f"{rede}_id"] = publicar(url, d["legenda"])
                print(f"{rede}: publicado {d[f'{rede}_id']}")
            except Exception:
                erro = True
                print(f"{rede}: ERRO\n{traceback.format_exc()}")
                if rede == "tt" and agora - quando > timedelta(hours=2):   # TikTok não segura a fila para sempre
                    d["tt_id"] = "erro: desisti depois de 2 h"
        # só sai da fila quando TODAS as redes pedidas no item postaram (rede pedida sem token = continua na fila)
        faltam = [r for r in (d.get("redes") or []) if not d.get(f"{r}_id")]
        if all(d.get(f"{r}_id") for r in ligadas) and not faltam:
            postados = json.loads(POSTADOS.read_text(encoding="utf-8")) if POSTADOS.exists() else []
            postados.append({k: d.get(k) for k in ("titulo", "youtube_id", "ig_id", "fb_id", "tt_id", "nc_id")} |
                            {"postado": agora.isoformat(timespec="seconds")})
            POSTADOS.write_text(json.dumps(postados, ensure_ascii=False, indent=1), encoding="utf-8")
            arq.unlink()
            (FILA / f"{arq.stem}.mp4").unlink(missing_ok=True)
            (FILA / f"{arq.stem}.jpg").unlink(missing_ok=True)
        else:
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    git = lambda *a: subprocess.run(["git", "-C", str(RAIZ), *a], check=True)
    git("config", "user.name", "robo-fatocontado")
    git("config", "user.email", "robo@users.noreply.github.com")
    git("add", "-A")
    if subprocess.run(["git", "-C", str(RAIZ), "diff", "--cached", "--quiet"]).returncode:
        git("commit", "-m", f"postado: {len(prontos)} item(ns)")
        git("push")
    if erro:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""TikTok (Content Posting API oficial, gratuita) para o robô do GitHub Actions.

Segredos: TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_REFRESH_TOKEN (o motor\\tiktok_autorizar.py grava os 3).
Variável do repositório TT_MODO (Settings > Variables):
  rascunho (padrão) -> vai para a caixa de entrada do TikTok; ele toca em "postar" no celular (escopo video.upload)
  privado           -> posta direto, visível só para ele (app ainda sem aprovação do TikTok)
  publico           -> posta direto para todo mundo (só depois que o TikTok aprovar o app)
Envia o arquivo direto (FILE_UPLOAD), então não precisa verificar o domínio do site.
"""
import math
import os
import time
from pathlib import Path

import requests

API = "https://open.tiktokapis.com/v2"
MODO = (os.environ.get("TT_MODO") or "rascunho").strip().lower()
_token = None


def token():
    global _token
    if _token:
        return _token
    r = requests.post(f"{API}/oauth/token/", timeout=60, data={
        "client_key": os.environ["TT_CLIENT_KEY"], "client_secret": os.environ["TT_CLIENT_SECRET"],
        "grant_type": "refresh_token", "refresh_token": os.environ["TT_REFRESH_TOKEN"]}).json()
    if "access_token" not in r:
        raise RuntimeError(f"TikTok não renovou o acesso ({r.get('error')}: {r.get('error_description')}) — "
                           "rode de novo o motor\\tiktok_autorizar.py")
    if r.get("refresh_token") and r["refresh_token"] != os.environ["TT_REFRESH_TOKEN"]:
        print("tt: AVISO o TikTok trocou a chave de renovação; rode o motor\\tiktok_autorizar.py para gravar a nova")
    _token = r["access_token"]
    return _token


def post(caminho, corpo):
    r = requests.post(f"{API}/{caminho}", json=corpo, timeout=120,
                      headers={"Authorization": f"Bearer {token()}",
                               "Content-Type": "application/json; charset=UTF-8"}).json()
    err = r.get("error") or {}
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok {caminho}: {err.get('code')} — {err.get('message')}")
    return r.get("data") or {}


def _legenda(texto):
    # TikTok aceita até 2200 caracteres; sem links (não viram clique e podem reduzir alcance)
    linhas = [l for l in texto.splitlines() if "http" not in l]
    return "\n".join(linhas).strip()[:2200]


def publicar_video(arquivo, legenda):
    arquivo = Path(arquivo)
    tam = arquivo.stat().st_size
    # pedaços de 10 MB; o último leva o resto (regra do TikTok: total = piso(tamanho / pedaço))
    pedaco = tam if tam <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    total = max(1, math.floor(tam / pedaco))
    fonte = {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": pedaco, "total_chunk_count": total}

    if MODO == "rascunho":
        d = post("post/publish/inbox/video/init/", {"source_info": fonte})
    else:
        info = post("post/publish/creator_info/query/", {})
        nivel = "PUBLIC_TO_EVERYONE" if MODO == "publico" else "SELF_ONLY"
        if nivel not in (info.get("privacy_level_options") or [nivel]):
            raise RuntimeError(f"TikTok não deixa postar como {nivel}: {info.get('privacy_level_options')}")
        d = post("post/publish/video/init/", {"source_info": fonte, "post_info": {
            "title": _legenda(legenda), "privacy_level": nivel, "disable_duet": False,
            "disable_comment": False, "disable_stitch": False, "video_cover_timestamp_ms": 1500}})

    with arquivo.open("rb") as f:
        for i in range(total):
            ini = i * pedaco
            fim = tam - 1 if i == total - 1 else ini + pedaco - 1
            f.seek(ini)
            dados = f.read(fim - ini + 1)
            r = requests.put(d["upload_url"], data=dados, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(dados)),
                "Content-Range": f"bytes {ini}-{fim}/{tam}"})
            if r.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok recusou o envio (pedaço {i + 1}/{total}): {r.status_code} {r.text[:200]}")

    for _ in range(60):
        time.sleep(10)
        st = post("post/publish/status/fetch/", {"publish_id": d["publish_id"]})
        s = st.get("status")
        if s == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or []
            return str(ids[0]) if ids else d["publish_id"]
        if s == "SEND_TO_USER_INBOX":
            return f"rascunho:{d['publish_id']}"
        if s == "FAILED":
            raise RuntimeError(f"TikTok falhou: {st.get('fail_reason')}")
    raise RuntimeError("TikTok demorou demais para processar")

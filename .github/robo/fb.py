"""Reels na página do Facebook (facebook.com/fatocontadobrasil) pela Graph API, a partir de um link público do vídeo."""
import os
import time

import requests

G = "https://graph.facebook.com/v21.0"
TOKEN = os.environ.get("FB_PAGE_TOKEN")
PAGE = os.environ.get("FB_PAGE_ID")


def na_pagina(token, page):
    """Devolve um publicar_reel que posta em OUTRA página (ex.: New Clipador, segredos NC_PAGE_TOKEN/NC_PAGE_ID)."""
    def publicar(*a, **k):
        global TOKEN, PAGE
        antes = TOKEN, PAGE
        TOKEN, PAGE = token, page
        try:
            return publicar_reel(*a, **k)
        finally:
            TOKEN, PAGE = antes
    return publicar


def _ok(r):
    d = r.json()
    if r.status_code >= 400 or "error" in d:
        raise RuntimeError(f"Facebook: {d.get('error', d)}")
    return d


def publicar_video(video_url, descricao, titulo, thumb_url=None):
    """Vídeo longo (3 a 10 min, melhor monetização) vai como vídeo normal da página, não como Reel, com a thumb."""
    files = None
    if thumb_url:
        r = requests.get(thumb_url, timeout=60)
        if r.status_code == 200:
            files = {"thumb": ("thumb.jpg", r.content, "image/jpeg")}
    d = _ok(requests.post(f"https://graph-video.facebook.com/v21.0/{PAGE}/videos", data={
        "file_url": video_url, "title": titulo, "description": descricao, "published": "true",
        "access_token": TOKEN}, files=files, timeout=600))
    return _esperar(d["id"])


def publicar_reel(video_url, descricao, titulo="", duracao=0, thumb_url=None):
    if duracao and duracao > 175:
        return publicar_video(video_url, descricao, titulo, thumb_url)
    ini = _ok(requests.post(f"{G}/{PAGE}/video_reels", params={"upload_phase": "start", "access_token": TOKEN},
                            timeout=60))
    vid = ini["video_id"]
    _ok(requests.post(ini.get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                      headers={"Authorization": f"OAuth {TOKEN}", "file_url": video_url}, timeout=300))
    _ok(requests.post(f"{G}/{PAGE}/video_reels", params={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": descricao,
        "access_token": TOKEN}, timeout=60))
    return _esperar(vid)


def _esperar(vid):
    for _ in range(60):
        time.sleep(10)
        st = _ok(requests.get(f"{G}/{vid}", params={"fields": "status", "access_token": TOKEN}, timeout=60))
        s = st.get("status", {})
        if s.get("video_status") == "ready" or s.get("publishing_phase", {}).get("status") == "complete":
            return vid
        if s.get("video_status") == "error":
            raise RuntimeError(f"Facebook recusou o vídeo: {s}")
    return vid  # ainda processando, mas já foi enviado para publicar

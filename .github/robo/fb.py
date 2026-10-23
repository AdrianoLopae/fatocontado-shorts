"""Reels na página do Facebook (facebook.com/fatocontadobrasil) pela Graph API, a partir de um link público do vídeo."""
import os
import time

import requests

G = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["FB_PAGE_TOKEN"]
PAGE = os.environ["FB_PAGE_ID"]


def _ok(r):
    d = r.json()
    if r.status_code >= 400 or "error" in d:
        raise RuntimeError(f"Facebook: {d.get('error', d)}")
    return d


def publicar_reel(video_url, descricao):
    ini = _ok(requests.post(f"{G}/{PAGE}/video_reels", params={"upload_phase": "start", "access_token": TOKEN},
                            timeout=60))
    vid = ini["video_id"]
    _ok(requests.post(ini.get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                      headers={"Authorization": f"OAuth {TOKEN}", "file_url": video_url}, timeout=300))
    _ok(requests.post(f"{G}/{PAGE}/video_reels", params={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": descricao,
        "access_token": TOKEN}, timeout=60))
    for _ in range(60):
        time.sleep(10)
        st = _ok(requests.get(f"{G}/{vid}", params={"fields": "status", "access_token": TOKEN}, timeout=60))
        s = st.get("status", {})
        if s.get("video_status") == "ready" or s.get("publishing_phase", {}).get("status") == "complete":
            return vid
        if s.get("video_status") == "error":
            raise RuntimeError(f"Facebook recusou o vídeo: {s}")
    return vid  # ainda processando, mas já foi enviado para publicar

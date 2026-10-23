"""Acesso ao Instagram (API com login do Instagram) para os robôs que rodam no GitHub Actions."""
import os
import time

import requests

API = "https://graph.instagram.com"
TOKEN = os.environ["IG_TOKEN"]
UID = os.environ["IG_USER_ID"]
EU = os.environ.get("IG_USERNAME", "fatocontadobrasil").lower()


def get(caminho, **params):
    params["access_token"] = TOKEN
    r = requests.get(f"{API}/{caminho}", params=params, timeout=60).json()
    if "error" in r:
        raise RuntimeError(f"{caminho}: {r['error'].get('message')}")
    return r


def post(caminho, data=None, json=None):
    r = requests.post(f"{API}/{caminho}", params={"access_token": TOKEN}, data=data, json=json, timeout=120).json()
    if "error" in r:
        raise RuntimeError(f"{caminho}: {r['error'].get('message')}")
    return r


def publicar_reel(video_url, legenda):
    cont = post(f"{UID}/media", data={"media_type": "REELS", "video_url": video_url, "caption": legenda,
                                      "share_to_feed": "true", "thumb_offset": "1500"})["id"]
    for _ in range(60):
        time.sleep(10)
        st = get(cont, fields="status_code,status")
        if st.get("status_code") == "FINISHED":
            return post(f"{UID}/media_publish", data={"creation_id": cont})["id"]
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram recusou o vídeo: {st}")
    raise RuntimeError("Instagram demorou demais para processar")

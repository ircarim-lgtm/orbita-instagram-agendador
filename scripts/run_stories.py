"""
run_stories.py - Publica os Stories do stories.json (5 por dia, em sequencia).

Roda pelo GitHub Actions. Regras:
  - o dia e publicado quando publish_at <= agora (ate MAX_LATE_HOURS de atraso);
  - os 5 Stories saem em ordem; cada um e registrado em published_stories.json
    logo depois de publicado, entao uma nova execucao continua de onde parou
    e nunca repete um Story;
  - DRY_RUN=true apenas confere as URLs e mostra o que seria publicado.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import publish_instagram as ig

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "stories.json"
PUBLISHED = ROOT / "published_stories.json"
MAX_LATE = timedelta(hours=float(os.getenv("MAX_LATE_HOURS", "8")))
REPO = os.getenv("GITHUB_REPOSITORY", "ircarim-lgtm/orbita-instagram-agendador")
MEDIA_BASE_URL = os.getenv(
    "MEDIA_BASE_URL", f"https://raw.githubusercontent.com/{REPO}/main"
).rstrip("/")


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def now_utc() -> datetime:
    override = os.getenv("FAKE_NOW")  # so para testes
    if override:
        return datetime.fromisoformat(override).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def image_url(rel: str) -> str:
    url = f"{MEDIA_BASE_URL}/{rel}"
    head = requests.head(url, allow_redirects=True, timeout=30)
    if head.status_code != 200:
        ig.fail(f"A imagem nao esta acessivel em {url} (HTTP {head.status_code}). "
                "O repositorio precisa ser PUBLICO.")
    return url


def with_retry(fn, *args, tries: int = 4, wait: int = 15):
    """A API do Instagram as vezes falha de forma passageira (ex.: codigo 24 logo apos criar a midia)."""
    for i in range(tries):
        try:
            return fn(*args)
        except SystemExit:
            if i == tries - 1:
                raise
            print(f"  Tentativa {i + 1}/{tries} falhou; nova tentativa em {wait}s...")
            time.sleep(wait)


def publish_story(url: str) -> str:
    key = "video_url" if url.lower().endswith(".mp4") else "image_url"
    data = ig.api("POST", f"{ig.IG_ID}/media", data={
        "media_type": "STORIES", key: url, "access_token": ig.TOKEN,
    })
    ig.wait_ready(data["id"], tries=24)
    return ig.media_publish(data["id"])


def main():
    dry = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    if not dry:
        ig.check_credentials()
    calendar = load(CALENDAR, [])
    published = load(PUBLISHED, {})
    now = now_utc()
    done_any = False
    for day in sorted(calendar, key=lambda d: d["publish_at"]):
        due = datetime.fromisoformat(day["publish_at"]).astimezone(timezone.utc)
        mine = published.setdefault(day["id"], {})
        pending = [i for i in range(len(day["images"])) if str(i + 1) not in mine]
        if due > now or not pending:
            continue
        if now - due > MAX_LATE:
            print(f"[{day['id']}] passou de {MAX_LATE} do horario; Stories deste dia NAO serao publicados.")
            continue
        print(f"[{day['id']}] {len(pending)} Story(s) para publicar")
        for i in pending:
            rel = day["images"][i]
            url = image_url(rel)
            if dry:
                print(f"  (simulacao) Story {i + 1}/{len(day['images'])}: {url}")
                continue
            mid = with_retry(publish_story, url)
            mine[str(i + 1)] = mid
            PUBLISHED.write_text(json.dumps(published, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Story {i + 1}/{len(day['images'])} publicado: {mid}")
            done_any = True
            time.sleep(4)
    if not done_any and not dry:
        print("Nada para publicar agora.")


if __name__ == "__main__":
    main()

"""
run_scheduled.py - Publica os posts do calendar.json cujo horario ja chegou.

Roda a cada 15 minutos pelo GitHub Actions. Regras:
  - publica o post se publish_at <= agora e ainda nao consta em published.json;
  - se o horario passou ha mais de MAX_LATE_HOURS, NAO publica (evita post fora de hora)
    e avisa com erro, para voce ver no GitHub;
  - cada post publicado e registrado em published.json logo em seguida.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import publish_instagram as ig

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "calendar.json"
PUBLISHED = ROOT / "published.json"
MAX_LATE = timedelta(hours=float(os.getenv("MAX_LATE_HOURS", "6")))
# O Instagram busca o video por uma URL publica. Usamos o proprio GitHub (raw).
REPO = os.getenv("GITHUB_REPOSITORY", "ircarim-lgtm/orbita-instagram-agendador")
MEDIA_BASE_URL = os.getenv(
    "MEDIA_BASE_URL", f"https://raw.githubusercontent.com/{REPO}/main"
).rstrip("/")


def public_url(rel: str) -> str:
    """URL publica de um arquivo do repo; confere que o Instagram vai conseguir baixar."""
    url = f"{MEDIA_BASE_URL}/{rel}"
    head = requests.head(url, allow_redirects=True, timeout=30)
    if head.status_code != 200:
        ig.fail(
            f"O arquivo nao esta acessivel em {url} (HTTP {head.status_code}). "
            "O repositorio precisa ser PUBLICO para o Instagram baixar a midia."
        )
    return url


def media_url(post: dict) -> str:
    return public_url(post["video"])


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def now_utc() -> datetime:
    override = os.getenv("FAKE_NOW")  # so para testes
    if override:
        return datetime.fromisoformat(override).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def already_on_instagram(caption: str):
    """Protecao contra post duplicado: se o Reels ja esta no perfil, devolve o id dele."""
    try:
        data = ig.api("GET", f"{ig.IG_ID}/media", params={
            "fields": "id,caption", "limit": "30", "access_token": ig.TOKEN,
        })
    except SystemExit:
        return None
    for m in data.get("data", []):
        if (m.get("caption") or "").strip() == caption.strip():
            return m["id"]
    return None


def due_posts(calendar: list, published: dict, now: datetime):
    """Devolve (para_publicar, perdidos)."""
    to_publish, missed = [], []
    for post in sorted(calendar, key=lambda p: p["publish_at"]):
        if post["id"] in published:
            continue
        when = datetime.fromisoformat(post["publish_at"])
        if now < when:
            continue
        (missed if now - when > MAX_LATE else to_publish).append(post)
    return to_publish, missed


def main() -> int:
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    calendar = load(CALENDAR, [])
    published = load(PUBLISHED, {})
    now = now_utc()
    print(f"Agora (UTC): {now.isoformat()}  |  dry_run={dry_run}")

    to_publish, missed = due_posts(calendar, published, now)
    for post in missed:
        print(f"::error::Post {post['id']} passou do horario ({post['publish_at']}) por mais "
              f"de {MAX_LATE} e NAO foi publicado. Publique manualmente ou ajuste o calendario.")
    if not to_publish:
        print("Nenhum post para publicar agora.")
        return 1 if missed else 0

    for post in to_publish:
        print(f"\n=== Publicando {post['id']}: {post['title']} ===")
        if dry_run:
            if post.get("images"):
                urls = [public_url(i) for i in post["images"]]
                print(f"[DRY RUN] Carrossel com {len(urls)} imagens acessiveis: {urls[0]} ...")
            else:
                ig.run_video(str(ROOT / post["video"]), post["caption"], dry_run=True)
            continue
        ig.check_credentials()
        existing = already_on_instagram(post["caption"])
        if existing:
            print(f"Este post ja esta no Instagram (id {existing}). Registrando e nao publicando de novo.")
            published[post["id"]] = {"post_id": existing, "published_at": "ja estava no perfil"}
            PUBLISHED.write_text(json.dumps(published, indent=2) + "\n", encoding="utf-8")
            continue
        if post.get("images"):
            creation_id = ig.publish_carousel([public_url(i) for i in post["images"]], post["caption"])
        else:
            creation_id = ig.publish_reel(media_url(post), post["caption"])
        post_id = ig.media_publish(creation_id)
        published[post["id"]] = {
            "post_id": post_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        PUBLISHED.write_text(json.dumps(published, indent=2) + "\n", encoding="utf-8")
        print(f"Publicado! Post ID: {post_id}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Publishes due SOMED.AI posts to Instagram through the Instagram API.

Reads schedule.json, publishes every post that is approved, due and not yet
published, then records it in published.json. Media is served from this
public repo via raw.githubusercontent.com, which is what Instagram downloads.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://graph.instagram.com/v23.0"
REPO_RAW = os.environ.get(
    "RAW_BASE", "https://raw.githubusercontent.com/eliavsudai/somedai-media/main"
)
TOKEN = os.environ.get("IG_TOKEN", "")
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(TOKEN, "***")
        raise RuntimeError(f"{method} {path} failed: {e.code} {body}") from None


def wait_ready(cid, timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        st = call("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {cid} status {st}")
        time.sleep(8)
    raise RuntimeError(f"container {cid} not ready after {timeout}s")


def url(p):
    return f"{REPO_RAW}/{urllib.parse.quote(p)}"


def media_kind(p):
    return "video" if p.lower().endswith((".mp4", ".mov")) else "image"


def create_container(ig, post):
    t, media, caption = post["type"], post["media"], post.get("caption", "")
    if t == "carousel":
        kids = []
        for m in media:
            args = {"is_carousel_item": "true"}
            if media_kind(m) == "video":
                args.update(media_type="VIDEO", video_url=url(m))
            else:
                args["image_url"] = url(m)
            cid = call("POST", f"{ig}/media", **args)["id"]
            wait_ready(cid)
            kids.append(cid)
        return call("POST", f"{ig}/media", media_type="CAROUSEL",
                    children=",".join(kids), caption=caption)["id"]
    if t == "image":
        return call("POST", f"{ig}/media", image_url=url(media[0]), caption=caption)["id"]
    if t == "reel":
        args = {"media_type": "REELS", "video_url": url(media[0]), "caption": caption,
                "share_to_feed": "true"}
        if post.get("cover"):
            args["cover_url"] = url(post["cover"])
        return call("POST", f"{ig}/media", **args)["id"]
    if t == "story":
        m = media[0]
        if media_kind(m) == "video":
            return call("POST", f"{ig}/media", media_type="STORIES", video_url=url(m))["id"]
        return call("POST", f"{ig}/media", media_type="STORIES", image_url=url(m))["id"]
    raise ValueError(f"unknown post type {t}")


def main():
    if not TOKEN and not DRY:
        sys.exit("IG_TOKEN secret is missing")
    sched = json.load(open(os.path.join(ROOT, "schedule.json")))
    state_path = os.path.join(ROOT, "published.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    now = dt.datetime.now(dt.timezone.utc)
    due = [p for p in sched["posts"]
           if p.get("approved") and p["id"] not in state
           and dt.datetime.fromisoformat(p["when"]) <= now]
    upcoming = [p for p in sched["posts"] if p["id"] not in state and p not in due]
    print(f"now {now.isoformat()} | due {len(due)} | upcoming {len(upcoming)}")
    for p in upcoming[:5]:
        print(f"  next: {p['when']} {p['id']} approved={p.get('approved', False)}")
    if not due:
        return
    ig = "me" if DRY else call("GET", "me", fields="user_id")["user_id"]
    changed = False
    for p in sorted(due, key=lambda x: x["when"]):
        missing = [m for m in p["media"] if not os.path.exists(os.path.join(ROOT, m))]
        if missing:
            print(f"SKIP {p['id']}: missing media {missing}")
            continue
        print(f"PUBLISH {p['id']} ({p['type']}, {len(p['media'])} media)")
        if DRY:
            continue
        try:
            cid = create_container(ig, p)
            wait_ready(cid)
            mid = call("POST", f"{ig}/media_publish", creation_id=cid)["id"]
            link = call("GET", mid, fields="permalink").get("permalink", "")
            state[p["id"]] = {"media_id": mid, "permalink": link,
                              "published_at": dt.datetime.now(dt.timezone.utc).isoformat()}
            changed = True
            print(f"  done: {link}")
        except Exception as e:  # keep going with other posts
            print(f"  ERROR {p['id']}: {e}")
    if changed:
        json.dump(state, open(state_path, "w"), indent=2)


if __name__ == "__main__":
    main()

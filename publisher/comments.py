"""Comment inbox for @somed.ai.book.

python3 publisher/comments.py list            -> new top-level comments (not yet handled) on recent posts
python3 publisher/comments.py reply ID "text" -> reply to a comment and mark it handled
python3 publisher/comments.py skip ID         -> mark handled without replying (spam, own comments, emoji-only)

Handled ids live in comments_state.json (local only, never committed: it can hold usernames).
"""
import json, os, sys, urllib.parse, urllib.request

API = "https://graph.instagram.com/v23.0"
TOKEN = os.environ.get("IG_TOKEN") or open("/home/claude/secure/somed_ig_token").read().strip()
STATE = "/home/claude/secure/somed_comments_state.json"


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}/{path}?{data}" if method == "GET" else f"{API}/{path}",
                                 data=None if method == "GET" else data.encode(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} failed: {e.code} {e.read().decode(errors='replace').replace(TOKEN, '***')}")


def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"handled": []}


def save(s):
    json.dump(s, open(STATE, "w"), indent=1)
    os.chmod(STATE, 0o600)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    s = load()
    if cmd == "list":
        me = call("GET", "me", fields="username")["username"]
        media = call("GET", "me/media", fields="id,caption,permalink,timestamp,comments_count", limit=15)["data"]
        for m in media:
            if not m.get("comments_count"):
                continue
            cs = call("GET", f"{m['id']}/comments",
                      fields="id,text,username,timestamp,replies{username,text}", limit=50).get("data", [])
            for c in cs:
                if c["id"] in s["handled"] or c.get("username") == me:
                    continue
                replied = any(r.get("username") == me for r in c.get("replies", {}).get("data", []))
                if replied:
                    continue
                print(json.dumps({"comment_id": c["id"], "user": c.get("username"), "text": c.get("text"),
                                  "at": c.get("timestamp"), "post": m["permalink"],
                                  "post_caption": (m.get("caption") or "")[:80]}, ensure_ascii=False))
    elif cmd == "reply":
        cid, text = sys.argv[2], sys.argv[3]
        r = call("POST", f"{cid}/replies", message=text)
        s["handled"].append(cid); save(s)
        print("replied", r.get("id"))
    elif cmd == "skip":
        s["handled"].append(sys.argv[2]); save(s)
        print("skipped")


if __name__ == "__main__":
    main()

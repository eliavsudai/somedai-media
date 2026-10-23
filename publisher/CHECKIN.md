# SOMED.AI check-in routine (for Claude's scheduled check-ins)

1. Publish check: `cd /home/claude/somedai-media && git pull -q && cat published.json`.
   Any approved post in schedule.json whose `when` has passed but isn't in published.json:
   publish it with `IG_TOKEN=$(cat /home/claude/secure/somed_ig_token) python3 publisher/publish.py`,
   then commit + push published.json.
   If graph.instagram.com is blocked, trigger GitHub instead:
   `gh api -X POST repos/eliavsudai/somedai-media/actions/workflows/publish.yml/dispatches -f ref=main -f 'inputs[dry_run]=false'`.
2. Comments: `python3 publisher/comments.py list`, then answer each in the account's voice:
   thoughtful, short, warm, curious about the reader's view; same language as the commenter; no hard selling.
   If asked whether the scenario is in the book: no, these are our own thought experiments inspired by its themes.
   Never invent book facts, quotes, prices or reviews. Spam/bots/self-promo: `comments.py skip ID` (never delete).
3. Tell the owner only if something needs him (a failed post, a question you can't answer).

# Nightly roadmap runner — how each scheduled run works

Window: 22:00–03:00 Asia/Muscat. A scheduled run fires every hour in that window. Each run:

1. Clone/pull `dwtgraphics-sys/kingbot`, `kingbot-ui`, `kingbot-syn` (push access).
2. Read `roadmap/progress.json`.
   - If `lock` is set and `lock.heartbeat` is less than 75 minutes old, another run is working: stop at once.
   - Otherwise set `lock = {"run": <session>, "since": <now>, "heartbeat": <now>}`, commit + push.
3. Take the pending items whose `start` time (Muscat) has passed tonight, in `seq` order, one at a time:
   - Set `status: "in_progress"`, push. Read the full prompt in `ROADMAP_v18.md` (section `### <ID>`).
   - Do the work. "Combines X through Y" items (MOD-06, EARN-05, UX-06, AI-04, GUIDE-04/24, TOOLS-08 …) = check that
     every part is really done and consistent, finish what is missing — never redo finished work.
   - Before writing: read the current code; keep every standing rule of the owner (below).
   - Test: Python compiles, `kingbot-ui/.github/check_html.js index.html` → `bad 0`, Playwright smoke test of the
     changed screen (local http.server + mocked api.github.com), GitHub checks green after push.
   - Bot code changes: bump `kingbot/version.json` (the server installs it after the checks pass).
   - Set `status: "done"` (or `"blocked"` + `note` with the reason), `finished` timestamp, refresh `lock.heartbeat`, push.
4. When nothing due is left: clear `lock`, push, and write a short Arabic summary (what was done / blocked) to
   `roadmap/reports/<date>.md`.

## Standing rules (from the owner — they win over any prompt text)
- Arabic UI; every new feature in the dashboard gets a ❗ info text.
- Never gems, never INSTANT; shops/donations with resources only; tavern free chests only.
- Never leave the game's Settings / Characters page open.
- Never commit secrets (github_token.txt, telegram*.txt, local_config.json, .env).
- Commander pictures only from `kingbot-ui/commanders` (the owner's own) — never from the internet.
- The assistant has NO floating button (the owner removed it on 25-11) — UX-05 "floating assistant trigger" means the
  menu entry / bottom-nav entry, not a floating button.
- Encryption (v196): never send plain settings to a server whose status is encrypted.
- `kingbot-ui/index.html` is one big file; another run or the owner may push at the same time → always
  `git pull --rebase` before push and re-run the checks after a rebase.

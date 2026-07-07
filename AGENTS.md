# For any AI coding agent — any vendor, any year

This is a pointer file. The real documents:

1. `README.md` — what this repo is and the tool conventions
2. `CONTINUITY.md` — the handoff document: invariants, change control,
   the rot playbook. **Read it before making structural decisions.**
3. `CLAUDE.md` — the verified-quirks ledger. Named for the tooling that
   started it; whichever model you are, treat it as the shared field
   notes and extend it when you verify something new.
4. The `README.md` of whichever tool you are touching.

Two facts to hold before your first edit: `main` is production (every
commit publishes the repo root to the live site), and `git log` on `main`
is the authoritative record of what actually happened.

# Setup: business acquisition search as a Claude Code project

## One-time setup

1. Install Claude Code if you haven't: `npm install -g @anthropic-ai/claude-code` (needs Node.js).
2. Create the project folder and drop `CLAUDE.md` in it:
   ```
   mkdir business-acquisition-search
   cd business-acquisition-search
   mkdir reports
   git init
   ```
   Copy `CLAUDE.md` from this delivery into that folder.
3. Test it interactively:
   ```
   claude
   ```
   Then type: `Run the acquisition search per CLAUDE.md.`
   Claude Code reads `CLAUDE.md` automatically as project context, so you don't need to re-paste the brief.

## Running it unattended (one-off)

From the project folder, in a terminal:
```
claude -p "Run the acquisition search per CLAUDE.md and save the report." --output-format text
```
`-p` runs Claude Code non-interactively (prints the result and exits) instead of opening a chat session.

## Scheduling it (Windows Task Scheduler)

Claude Code has no built-in scheduler — Cowork's recurring-task feature doesn't carry over. To get a weekly run:

1. Open Task Scheduler → Create Basic Task.
2. Trigger: Weekly, whatever day/time you want.
3. Action: "Start a program."
   - Program/script: `claude`
   - Add arguments: `-p "Run the acquisition search per CLAUDE.md and save the report." --output-format text`
   - Start in: the full path to your `business-acquisition-search` folder (this matters — it's how Claude Code finds `CLAUDE.md`).
4. Save. Optionally check "Run whether user is logged on or not" if you want it to fire even when you're not at the machine — you'll need to store credentials for that.

## Keeping history

Since reports land in `reports/YYYY-MM-DD.md` inside a git repo, commit after each run (`git add reports/ && git commit -m "acquisition search run"`) if you want a diffable trail of what showed up over time. You could also add a line to the end of the Task Scheduler command to auto-commit, e.g. chain a small `.bat`/`.ps1` wrapper that runs the `claude -p` command and then `git add`/`git commit`.

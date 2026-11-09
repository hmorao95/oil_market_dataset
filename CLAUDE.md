# CLAUDE.md

This project's agent instructions live in [AGENTS.md](AGENTS.md). Read and follow
them.

@AGENTS.md

Key reminders for this repo:

- Run the full quality gate before committing (see AGENTS.md).
- Branch, open a PR, squash-merge when CI is green.
- `outputs/` is committed and always rebuilt from `data/raw`, never edited by
  hand; commit both together.
- Releases bump the version in `pyproject.toml`, `CITATION.cff` and `uv.lock`
  together.

# Claude Skills

A personal collection of custom skills for Claude Code.

## Skills

### python-pro

The original Python skill, made by [Jeffallan](https://github.com/Jeffallan). Type-annotated Python with mypy, pytest, black, and ruff.

### python-pro-max

My fork of `python-pro`, adapted to my own conventions: async-first code, Pydantic and pydantic-settings, uv packaging in a flat app layout, Fire CLIs, and MongoDB via the Beanie ODM.

See [`examples/`](examples/) for a sample app using these conventions.

## Installation

```sh
make install        # skill + hook
make update-skill   # copy python-pro-max to ~/.claude/skills/
make install-hook   # install the hook and register it in settings.json
make help           # list targets
```

`install-hook` copies the script to `~/.claude/hooks/` and adds a `PreToolUse` entry to
`~/.claude/settings.json` only if that command isn't registered yet, so it's safe to re-run.
It backs the file up to `settings.json.bak` before touching it. Requires `jq`.

## Hooks

### enforce-python-pro-max

A `PreToolUse` hook on `Write|Edit`. When the file being written is a `.py`, it injects the
contents of `~/.claude/skills/python-pro-max/SKILL.md` as additional context, so the conventions
are in scope for the edit itself rather than only when the skill is explicitly invoked. It
deliberately sets no `permissionDecision` — normal permission prompts still apply.

## Adding skills

This repo is where I collect the skills I actually use. Each skill lives in its own directory with a `SKILL.md`.

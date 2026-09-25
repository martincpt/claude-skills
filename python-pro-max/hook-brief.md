# python-pro-max — pre-write checklist (full rules: ~/.claude/skills/python-pro-max/SKILL.md, references/)

Before writing this file, check every line against these. Each is a rule people keep breaking.

CALL SITES (references/call-site-style.md)
- NAME the object: `repository = Repo()` then `await repository.get(x)`. Never `Repo().get(x)` / `await Svc().run()`.
- NAME the iterable: `stages = (A, B)` then `for s in stages:`. Never a literal tuple/list in a `for` header.
- NAME each step of a chain that does real work: `out = task_output(p)` first, not `f(g(h(x)))`.
- Call wraps across lines -> KEYWORD arguments (`run_stage(items=..., stage=..., task=...)`). Positional only if it fits one line and the meaning is obvious.
- Name a value before `.append()`/`.extend()` of it. A single expr that only builds a value for its one consumer/`return` needs no name.

STRUCTURE
- Blank lines between setup / main logic / return; never jam a `for`/`if` against the lines it consumes.
- Loose helper functions -> `@staticmethod` under a domain class.
- Instance attrs declared at class level (`name: str`), assigned in `__init__`.
- `message = "..."` then `raise X(message)`. One-line docstrings. Relative imports inside own package.
- Data with known keys -> Pydantic model, not dict. Beanie: operators, never `{"$set": ...}`.

SELF-CHECK (grep your own diff before saving)
- `[A-Z]\w*\(\)\.\w+\(`   constructed-and-called-in-one-expression
- `for \w+ in \(|\[`      literal collection in a loop header
- a multi-line call whose arguments are all bare positionals

# AGENTS.md

## Project

`taco` is a single-file Python 3 stdin filter that wraps file paths in **OSC 8 terminal hyperlinks**. The whole tool is `taco.py` (stdlib only). Pipe `git`/`diff`/`grep` output through it and file paths become clickable.

## Commands

Run the standalone tests (no third-party deps):
```
python3 tests/test_taco.py
```

Lint (matches CI):
```
pip install ruff
ruff check .
```

CI runs both test layers and ruff on every push/PR via `.github/workflows/ci.yml` (Python 3.10/3.11/3.12, ubuntu). Ruff settings live in `pyproject.toml`.

`install.sh` copies `taco.py` to `/usr/bin/taco` (uses sudo if `/usr/bin` isn't writable). Re-runs are idempotent if the file is unchanged.

## Architecture

`taco.py` is class-based. `TransformerFactory` composes an ordered tuple of `LineHandler` subclasses, and `LineTransformer` walks it, returning the first non-`None` result. Each handler implements `handle(*, line, context)` and returns `None` for lines it doesn't recognise. `LineContext` carries the `PathResolver`, `UrlTemplate`, and `StreamState` collaborators.

Most simple shapes subclass `SinglePathHandler` (one path, one capture group) or `TwoPathHandler` (`a/` and `b/` paths). `RegexHandler` owns pattern matching.

When adding a new line shape:
1. Add a `LineHandler` (or `SinglePathHandler` / `RegexHandler`) subclass that returns `None` for non-matches.
2. Register it in `TransformerFactory.create` (order matters: specific shapes before catch-alls like `HunkContentHandler` / `BarePathHandler`).
3. Use `Ansi.anchored(body=...)` for `^`-anchored patterns so `git diff --color=always` (which prefixes lines with `\x1b[1m` etc.) is still recognised.
4. After matching, use `match.span(n)` (positions in the **original** line, ANSI codes included) to splice the OSC 8 wrap back into `line` with `Osc8Link.wrap()`.

`PathResolver.resolve(path=...)` returns `None` for paths that escape the repo root — handlers must check this and return the original `line` unchanged where appropriate. `--- /dev/null` and `+++ /dev/null` are explicitly skipped (not real files).

`LineTransformer.transform_line` short-circuits when `OSC in line`, so the tool is **idempotent** — running `taco | taco` is a no-op after the first pass.

`Application` orchestrates config loading, template selection, and the filter itself. When stdout is a terminal (and `--no-pager` was not passed), `PagerSelector` chooses a command and `PagerRunner` pipes the transformed stream into it. The command comes from `--pager`, `$TACO_PAGER`, `$PAGER`, then `less`; `less` gets `-R` and `LESS=FRX` when `LESS` is unset. A pager that exits early (user presses `q`) is treated as success, not a traceback. Non-TTY stdout always writes directly.

## Tests

`tests/test_taco.py` is a self-contained script (no pytest, no harness) that imports `taco` and drives `TransformerFactory` / `LineTransformer` directly. It uses a hard-coded `ROOT = "/home/dev/project"` literal and expects link targets to match `file:///home/dev/project/...`. The `t(line)` helper builds a transformer and adds the trailing `\n` (handlers expect it). `visible(text)` strips both OSC 8 sequences and ANSI SGR codes; `urls(text)` returns the URL payloads.

## Conventions

- **No comments in code** unless the user asks.
- The module level contains only imports and class definitions. Behaviour and constants live on the class that owns them; do not add module-level functions or `UPPER_SNAKE` constants.
- Don't add a `requirements.txt`; `taco.py` is stdlib-only by design. `ruff` is dev-only and listed in `.github/workflows/ci.yml`.
- `__pycache__` is gitignored.
- Preset CLI flags (`--atom`, `--code`, `--emacs`, `--nano`, `--phpstorm`, `--pycharm`, `--pycharm-community`, `--subl`, `--vim`, `--webstorm`, `--windsurf`) write the matching template from `TemplateCatalog.PRESETS` to `ConfigStore.CONFIG_PATH` and reuse it on subsequent runs.
- `--template URL` is a one-off override and does **not** touch the config file.  `--template` and preset flags are mutually exclusive (argparse group).
- `{path}` and `{file}` are interchangeable placeholders for the file path in the template; both must be supported by `UrlTemplate`.
- Tests override `HOME` in the subprocess environment and pass explicit `ConfigStore(path=...)` instances for in-process config checks.
- Pager tests use a real pty (`pty.openpty`) plus a tiny shell-script pager so paging behaviour is exercised without depending on `less`.
- `--pager` only controls which command is used; it does not force paging when stdout is not a terminal. `--pager` and `--no-pager` are mutually exclusive.

![GitHub language](https://img.shields.io/github/languages/top/TangoMan75/taco)
![GitHub license](https://img.shields.io/github/license/TangoMan75/taco)
[![GitHub release](https://img.shields.io/github/v/release/TangoMan75/taco?sort=semver)](https://github.com/TangoMan75/taco/releases/)
[![GitHub release date](https://img.shields.io/github/release-date/TangoMan75/taco)](https://github.com/TangoMan75/taco/releases/)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/TangoMan75/taco)
[![CI status](https://github.com/TangoMan75/taco/workflows/Python/badge.svg)](https://github.com/TangoMan75/taco/actions/workflows/python.yml)
![GitHub stars](https://img.shields.io/github/stars/TangoMan75/taco)
![Visitors](https://api.visitorbadge.io/api/visitors?path=https%3A%2F%2Fgithub.com%2FTangoMan75%2Ftaco&labelColor=%23697689&countColor=%2337d67a&style=flat)

Taco
===

![Taco](./taco.svg)

Make file paths in terminal output clickable OSC 8 hyperlinks.
----------------------------------------------------------------

Pipe `git`, `diff` or `grep` output through `taco` and every file path it recognises becomes a link that opens in your editor, at the right line when the input carries one. Single-file Python, standard library only.

🌐 [github.com/TangoMan75/taco](https://github.com/TangoMan75/taco)
------------------------------------------------------------------

🚀 Features
-----------

### ⚡ Clickable diff and grep output

1. **Wide line-shape coverage:** recognises `diff --git`, `---`/`+++`, `Binary files`, `rename`/`copy`, `git log --stat`, `git status --porcelain`, hunk headers, `grep path:line:text` and bare paths.
2. **Line-aware links:** `grep` matches and hunk headers jump to the first changed line of the new file, not just the top of the file.
3. **Repository-scoped resolution:** relative paths resolve against the Git root and paths that escape it are left untouched.

### ⚡ Editor integration

1. **Presets for 11 editors:** Atom, VS Code, Emacs, Nano, PhpStorm, PyCharm, PyCharm Community, Sublime Text, Vim, WebStorm and Windsurf.
2. **Persistent choice:** one preset flag writes the template to `~/.config/TangoMan75/taco/config.json` and every later run reuses it.
3. **One-off templates:** `--template` accepts any URL scheme with `{path}`/`{file}` and optional `{line}` placeholders, without touching the config.

### ⚡ Safe by design

1. **Idempotent:** output that already contains OSC 8 sequences is passed through, so `taco | taco` is a no-op after the first pass.
2. **Non-destructive paging:** colours and hyperlinks survive `less -R`; redirected output is never paged.
3. **No crash on bad input:** malformed configs, missing pagers and broken pipes are reported or ignored, never fatal.

📡 Supported line shapes
------------------------

1. **Diff headers:** `diff --git a/x b/x`, `--- a/x`, `+++ b/x`, `Binary files a/x and b/x differ`.
2. **Git metadata:** `rename from`/`rename to`, `copy from`/`copy to`, `git log --stat` rows and `git status --porcelain` columns.
3. **Hunks:** `@@ -old[,n] +new[,n] @@` links to the current file at the first modified line of the new file.
4. **Search results:** `path:line: text` from `grep -n` and `git grep -n`.
5. **Plain paths:** a line that is nothing but a path is linked whole.

Commit messages, hunk content and unrecognised text pass through byte-for-byte. `/dev/null` is never linked.

📦 Installation
---------------

1. **Clone the repository:**

   ```bash
   git clone https://github.com/TangoMan75/taco.git
   cd taco
   ```

2. **Run the installer:**

   ```bash
   ./entrypoint install
   ```

   It copies `taco.py` to `/usr/bin/taco`, using `sudo` when needed, and skips the copy when the installed file is already identical. The script also runs `git config --global core.pager 'taco'`, so `git` output is filtered automatically from then on.

3. **Verify:**

   ```bash
   taco --help
   ```

   To skip the Git pager change, copy the file yourself instead:

   ```bash
   sudo install -m 755 taco.py /usr/bin/taco
   ```

🛠️ Usage
--------

1. **Pipe a command through it:**

   ```bash
   git diff | taco
   git log -p | taco
   git status | taco
   grep -rn "TODO" . | taco
   ```

2. **Pick an editor once:**

   ```bash
   taco --code      # VS Code
   taco --vim
   taco --pycharm
   ```

   The template persists in `~/.config/TangoMan75/taco/config.json`.

3. **Override for a single run:**

   ```bash
   grep -rn foo . | taco --template 'vscode://file/{path}:{line}'
   ```

4. **Control paging.** When stdout is a terminal, output goes through a pager (`less -R` by default). Redirected stdout is written directly, so `git diff | taco > patch.diff` still works.

   ```bash
   git diff | taco --no-pager        # write straight to the terminal
   git diff | taco --pager 'less -S' # custom pager command
   ```

   The pager command comes from `--pager`, then `$TACO_PAGER`, then `$PAGER`, then `less`. When `LESS` is unset, `less` is started with `FRX`: quit if the output fits on one screen, keep raw colours, do not clear the screen on exit.

### Options

|          Flag         |             Default             |                                    Description                                     |
|-----------------------|---------------------------------|------------------------------------------------------------------------------------|
| `--template URL`      | config `default_template`       | URL template with `{path}`/`{file}` and optional `{line}` (one-off, not persisted) |
| `--atom`              | —                               | Use the Atom preset (persists)                                                     |
| `--code`              | —                               | Use the VS Code preset (persists)                                                  |
| `--emacs`             | —                               | Use the Emacs preset (persists)                                                    |
| `--nano`              | —                               | Use the Nano preset (persists)                                                     |
| `--phpstorm`          | —                               | Use the PhpStorm preset (persists)                                                 |
| `--pycharm`           | —                               | Use the PyCharm preset (persists)                                                  |
| `--pycharm-community` | —                               | Use the PyCharm Community preset (persists)                                        |
| `--subl`              | —                               | Use the Sublime Text preset (persists)                                             |
| `--vim`               | —                               | Use the Vim preset (persists)                                                      |
| `--webstorm`          | —                               | Use the WebStorm preset (persists)                                                 |
| `--windsurf`          | —                               | Use the Windsurf preset (persists)                                                 |
| `--root PATH`         | auto-detected via `git`         | Repository root for resolving paths                                                |
| `--pager CMD`         | `$TACO_PAGER`, `$PAGER`, `less` | Pager command used when stdout is a terminal                                       |
| `--no-pager`          | —                               | Write directly to stdout instead of paging                                         |

`--template` and the preset flags are mutually exclusive, and so are `--pager` and `--no-pager`.

### Persistent config

Presets write `default_template` to `~/.config/TangoMan75/taco/config.json`:

```json
{
    "default_template": "code://open?url=file:///{file}&line={line}"
}
```

- The file is created the first time a preset flag runs.
- With no `--template` or preset flag, runs read `default_template` and fall back to `file:///{path}` when the file is missing or the value is empty.
- A malformed config prints a warning on stderr and the built-in default is used — no crash.
- Both `{path}` and `{file}` are accepted for the file path; `{path}`/ `{file}` carry the absolute path without its leading slash. If the template has no `{line}`, a `#line` fragment is appended when a line is known.

🖇️ Dependencies / Requirements
------------------------------

1. **Python 3.10+:** the whole tool is a single stdlib-only script; no packages to install.
2. **Git (recommended):** used to auto-detect the repository root. When it is unavailable, the current working directory is used unless `--root` is passed.
3. **A pager (optional):** `less` is the default; any executable named by `--pager`, `$TACO_PAGER` or `$PAGER` also works. Non-terminal stdout needs none.
4. **ruff (development only):** used by CI for linting.

🐞 Troubleshoot
---------------

1. **Links show as plain text:** the terminal must support OSC 8. Test with `printf '\e]8;;https://example.com\e\\click\e]8;;\e\\\n'`; if that is not clickable, the terminal (or multiplexer) lacks support.
2. **`taco: pager not found`:** install `less` or select another pager with `--pager`, `$TACO_PAGER`, `$PAGER`, or bypass paging with `--no-pager`.
3. **Links point at the wrong directory:** pass `--root` explicitly, or run the command inside the Git repository whose root should be used.
4. **Nothing is linked:** `taco` only recognises the line shapes listed above, and paths outside the repository root are deliberately skipped.
5. **Git behaves unexpectedly after `./install.sh`:** the installer sets `core.pager` globally. Undo with `git config --global --unset core.pager`.
6. **`taco: ignoring malformed config ...`:** repair or delete `~/.config/TangoMan75/taco/config.json`; the built-in default takes over meanwhile.

🧪 Testing Strategy
-------------------

1. **Standalone suite:** `python3 tests/test_taco.py` drives `TransformerFactory` and `LineTransformer` directly with no pytest or third-party harness, covering diff/grep/status shapes, presets, config persistence, pager selection, broken pipes and idempotency.
2. **Behavioural spec:** `features/taco.feature` documents the expected behaviour as Gherkin scenarios and is linted in CI.
3. **Lint:** `pip install ruff && ruff check .`.
4. **CI:** GitHub Actions runs the test suite on Python 3.10, 3.11 and 3.12, plus the ruff job, for every push and pull request to `main`.

🐛 Limitations
--------------

1. ⚠️ **Known shapes only:** prose or custom log formats are passed through unchanged; extend the handler chain in `taco.py` to add new shapes.
2. ⚠️ **Terminal support required:** OSC 8 links need a capable terminal and are silently inert elsewhere.
3. ⚠️ **Repository-root scoped:** paths that resolve outside the root are never linked, and the root must be correct for links to work.
4. ⚠️ **Idempotent short-circuit:** any line already containing an OSC 8 sequence is skipped, so a second pass cannot retarget existing links.
5. ⚠️ **Installer changes Git config:** `install.sh` sets the global Git pager, which affects every repository on the machine.

📝 Notes
--------

`taco.py` reads stdin line by line and walks an ordered chain of handler classes. Each handler returns `None` when it does not recognise a line; the first non-`None` result wins. `LineContext` carries the `PathResolver`, the `UrlTemplate` and a per-stream `StreamState`, which remembers the current file so hunk headers and context lines can refer back to it. Hunk headers link to `new_start` (plus the three usual context lines) so a click lands on the first changed line.

The default template is `file:///{path}`; presets use `<scheme>://open?url=file:///{file}&line={line}`.

🤝 Contributing
---------------

Thank you for your interest in contributing to **Taco**.

Please open an issue first for bugs or feature ideas, and check whether one already exists in the [issue tracker](https://github.com/TangoMan75/taco/issues).
Pull requests should keep the codebase stdlib-only, preserve the class-based handler chain, and pass both `python3 tests/test_taco.py` and `ruff check .`.
Project conventions are documented in [AGENTS.md](./AGENTS.md).

📜 License
----------

Copyrights (c) 2026 "Matthias Morin" <mat@tangoman.io>

[![License](https://img.shields.io/badge/Licence-MIT-green.svg)](LICENSE) Distributed under the MIT license.

If you like **Taco** please star, follow or tweet:

[![GitHub stars](https://img.shields.io/github/stars/TangoMan75/taco?style=social)](https://github.com/TangoMan75/taco/stargazers)
[![GitHub followers](https://img.shields.io/github/followers/TangoMan75?style=social)](https://github.com/TangoMan75)
[![Twitter](https://img.shields.io/twitter/url?style=social&url=https%3A%2F%2Fgithub.com%2FTangoMan75%2Ftaco)](https://twitter.com/intent/tweet?text=Wow:&url=https%3A%2F%2Fgithub.com%2FTangoMan75%2Ftaco)

🙏 Acknowledgements
-------------------

- **Python standard library:** everything from argument parsing to subprocess paging is stdlib, so there is nothing to install.
- **OSC 8:** the terminal hyperlink escape sequence that makes the whole idea work.
- **Git and GNU less:** the tools whose output `taco` is built to read and page.

👋 Let's Build Your Next Project Together !
-------------------------------------------

Clean code. Clear communication.

From first sketch to final launch, I've got your back.

[![tangoman.io](https://img.shields.io/badge/✉️%20Get%20in%20touch%20now%20!-FD9400?style=for-the-badge)](https://tangoman.io)

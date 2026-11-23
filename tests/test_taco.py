#!/usr/bin/env python3
"""Standalone verification of taco.py against specs/taco.feature.

Run with:  python3 tests/test_taco.py
No third-party dependencies required.
"""

import json
import os
import pty
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import taco

ROOT = "/home/dev/project"
OSC = taco.Osc8Link.OSC
ST = taco.Osc8Link.ST
DEFAULT = taco.TemplateCatalog.DEFAULT
# SGR escape sequences emitted by `git diff --color=always`.
BOLD = "\x1b[1m"
CYAN = "\x1b[36m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
RST = "\x1b[m"

# Isolated config path so CLI tests never touch the user's real config.
# Subprocess tests redirect HOME to a temp directory so
# ~/.config/TangoMan75/taco/config.json resolves to the test location.
TEST_HOME = tempfile.mkdtemp(prefix="taco-test-")
os.makedirs(os.path.join(TEST_HOME, ".config", "TangoMan75", "taco"), exist_ok=True)
CONFIG_PATH = os.path.join(TEST_HOME, ".config", "TangoMan75", "taco", "config.json")

passed = 0
failed = 0
failures = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        failures.append(f"{name}: {detail}")


def transform(line, root=ROOT, template=DEFAULT, state=None):
    transformer = taco.TransformerFactory().create(root=root, template=template)
    return transformer.transform_line(line=line, state=state)


def t(line, root=ROOT, template=DEFAULT):
    return transform(line + "\n", root, template)


def transform_stream(stdin, stdout, root=ROOT, template=DEFAULT):
    transformer = taco.TransformerFactory().create(root=root, template=template)
    transformer.transform_stream(stdin=stdin, stdout=stdout)


def visible(text):
    """Strip OSC 8 escape sequences (and their URL payload) and ANSI SGR
    color codes from text, leaving only the printable payload."""
    no_osc = re.sub(re.escape(OSC) + ".*?" + re.escape(ST), "", text)
    return taco.Ansi.SGR_RE.sub("", no_osc)


def urls(text):
    """Return list of URL targets embedded in text (closing markers excluded)."""
    return [u for u in re.findall(re.escape(OSC) + "(.*?)" + re.escape(ST), text) if u]


# 1. git diff header
out = t("diff --git a/src/app.py b/src/app.py")
check("1 contains OSC", OSC in out, repr(out))
check("1 target", urls(out) == ["file:///home/dev/project/src/app.py", "file:///home/dev/project/src/app.py"], str(urls(out)))
check("1 visible", visible(out) == "diff --git a/src/app.py b/src/app.py\n", repr(visible(out)))

# 2. --- a/path
out = t("--- a/src/app.py")
check("2 wrapped", OSC + "file:///home/dev/project/src/app.py" + ST + "a/src/app.py" in out, repr(out))
check("2 target", "file:///home/dev/project/src/app.py" in urls(out), str(urls(out)))

# 3. +++ b/path
out = t("+++ b/src/app.py")
check("3 wrapped", OSC + "file:///home/dev/project/src/app.py" + ST + "b/src/app.py" in out, repr(out))
check("3 target", "file:///home/dev/project/src/app.py" in urls(out), str(urls(out)))

# 4. both sides independently
out = t("diff --git a/old.py b/new.py")
check("4 a-link", "file:///home/dev/project/old.py" in urls(out), str(urls(out)))
check("4 b-link", "file:///home/dev/project/new.py" in urls(out), str(urls(out)))

# 5. plain diff -u
plain = "--- a.txt\t2024-01-01 10:00:00.000000000 +0100\n"
plain2 = "+++ b.txt\t2024-01-01 10:00:00.000000000 +0100\n"
hunk = "@@ -1 +1 @@\n"
out1 = transform(plain, ROOT, DEFAULT)
out2 = transform(plain2, ROOT, DEFAULT)
outh = transform(hunk, ROOT, DEFAULT)
check("5 a.txt link", "file:///home/dev/project/a.txt" in urls(out1), repr(out1))
check("5 b.txt link", "file:///home/dev/project/b.txt" in urls(out2), repr(out2))
check("5 hunk unchanged", outh == hunk, repr(outh))

# 6. /dev/null untouched
out1 = t("--- a/src/app.py")
out2 = t("+++ /dev/null")
check("6 a wrapped", OSC in out1, repr(out1))
check("6 devnull untouched", OSC not in out2 and out2 == "+++ /dev/null\n", repr(out2))

# 7. outside repo
out = t("--- a/../../etc/passwd")
check("7 no OSC", OSC not in out, repr(out))
check("7 unchanged", out == "--- a/../../etc/passwd\n", repr(out))

# 8. grep -n
out = t("src/app.py:42:    return foo()")
check("8 target base", any(u.startswith("file:///home/dev/project/src/app.py") for u in urls(out)), str(urls(out)))
check("8 line fragment", any("#42" in u for u in urls(out)), str(urls(out)))

# 9. git grep -n
out = t("src/app.py:42:    return foo()")
check("9 visible", visible(out) == "src/app.py:42:    return foo()\n", repr(visible(out)))
check("9 target", any(u.startswith("file:///home/dev/project/src/app.py") for u in urls(out)), str(urls(out)))

# 10. git log --stat
out = t(" src/app.py | 4 ++--")
check("10 wrapped", "src/app.py" in out and OSC in out and visible(out) == " src/app.py | 4 ++--\n", repr(out))

# 11. git status porcelain
out = t("M  src/app.py")
check("11 wrapped", OSC in out and visible(out) == "M  src/app.py\n", repr(out))

# 12. git show --name-only
out = t("src/app.py")
check("12 wrapped line", out == OSC + "file:///home/dev/project/src/app.py" + ST + "src/app.py" + OSC + ST + "\n", repr(out))

# 13. rename
out1 = t("rename from old/name.py")
out2 = t("rename to new/name.py")
check("13 from", "file:///home/dev/project/old/name.py" in urls(out1), repr(out1))
check("13 to", "file:///home/dev/project/new/name.py" in urls(out2), repr(out2))

# 14. copy
out1 = t("copy from src.py")
out2 = t("copy to dst.py")
check("14 from", "file:///home/dev/project/src.py" in urls(out1), repr(out1))
check("14 to", "file:///home/dev/project/dst.py" in urls(out2), repr(out2))

# 15. binary
out = t("Binary files a/img.png and b/img.png differ")
check("15 a", "file:///home/dev/project/img.png" in urls(out), str(urls(out)))
check("15 b", urls(out).count("file:///home/dev/project/img.png") == 2, str(urls(out)))

# 16. commit metadata unchanged
meta = "commit efd941c9d07aa5e555e38f0c1d0662132c52d1b0 (HEAD -> main)\n"
meta2 = "Author: Matthias Morin <mat@tangoman.io>\n"
meta3 = "Date:   Mon Jun 22 19:03:22 2026 +0200\n"
for i, m in enumerate((meta, meta2, meta3), 1):
    o = transform(m, ROOT, DEFAULT)
    check(f"16.{i} unchanged", o == m, repr(o))

# 17. hunk content unchanged
hunks = [
    "@@ -0,0 +1,3 @@\n",
    "+#!/usr/bin/env python3\n",
    "+\n",
    "+def main():\n",
]
for i, h in enumerate(hunks, 1):
    o = transform(h, ROOT, DEFAULT)
    check(f"17.{i} unchanged", o == h, repr(o))

# 18. custom scheme with line
tmpl = "pycharm-community://open?url=file:///{path}&line={line}"
for inp in ("diff --git a/src/app.py b/src/app.py", "--- a/src/app.py", "+++ b/src/app.py"):
    o = t(inp, template=tmpl)
    check(f"18 starts ({inp})", all(u.startswith("pycharm-community://open?url=file:///") for u in urls(o)), str(urls(o)))
    check(f"18 line=1 ({inp})", all("&line=1" in u for u in urls(o)), str(urls(o)))

# 19. custom scheme without line placeholder
tmpl = "vscode://file/{path}:1"
out = t("--- a/src/app.py", template=tmpl)
check("19 target", urls(out) == ["vscode://file/home/dev/project/src/app.py:1"], str(urls(out)))

# 20. explicit root
out = t("--- a/app.py", root="/srv/code")
check("20 target", urls(out) == ["file:///srv/code/app.py"], str(urls(out)))

# 24. single-char name
out = t("--- a/a")
check("24 transformed", OSC in out, repr(out))
check("24 target", urls(out) == ["file:///home/dev/project/a"], str(urls(out)))

# 25. idempotency
once = t("--- a/src/app.py")
twice = transform(once, ROOT, DEFAULT)
check("25 idempotent", twice == once, repr(twice))
check("25 single transform", once.count(OSC) == 2 and twice.count(OSC) == 2, f"{once.count(OSC)}/{twice.count(OSC)}")


# ----------------------------------------------------------------------
# Colored output (git diff --color=always): SGR sequences must not stop
# file paths from being recognised and hyperlinked.
# ----------------------------------------------------------------------

# 26. colored `diff --git` header
out = t(BOLD + "diff --git a/src/app.py b/src/app.py" + RST)
check("26 colored diff header has OSC", OSC in out, repr(out))
check("26 colored diff header targets",
      urls(out).count("file:///home/dev/project/src/app.py") == 2,
      str(urls(out)))
check("26 colored diff header preserves bold",
      BOLD in out and RST in out, repr(out))

# 27. colored `---` line
out = t(BOLD + "--- a/src/app.py" + RST)
check("27 colored --- wrapped",
      OSC + "file:///home/dev/project/src/app.py" + ST + "a/src/app.py" in out,
      repr(out))
check("27 colored --- preserves bold and reset",
      out.startswith(BOLD) and RST in out, repr(out))

# 28. colored `+++` line
out = t(BOLD + "+++ b/src/app.py" + RST)
check("28 colored +++ wrapped",
      OSC + "file:///home/dev/project/src/app.py" + ST + "b/src/app.py" in out,
      repr(out))

# 29. colored `---` with timestamp (e.g. plain `diff -u`)
out = t(BOLD + "--- a.txt\t2024-01-01 10:00:00.000000000 +0100" + RST)
check("29 colored --- timestamp wrapped",
      OSC + "file:///home/dev/project/a.txt" + ST + "a.txt" in out,
      repr(out))
check("29 colored --- timestamp visible",
      visible(out).endswith("a.txt\t2024-01-01 10:00:00.000000000 +0100\n"),
      repr(visible(out)))

# 30. colored `Binary files` line
out = t(BOLD + "Binary files a/img.png and b/img.png differ" + RST)
check("30 colored binary wrapped",
      urls(out).count("file:///home/dev/project/img.png") == 2,
      str(urls(out)))

# 31. colored `rename from` / `rename to`
out = t(BOLD + "rename from old/name.py" + RST)
check("31 colored rename from",
      "file:///home/dev/project/old/name.py" in urls(out), str(urls(out)))

# 32. colored `copy from`
out = t(BOLD + "copy from src.py" + RST)
check("32 colored copy from",
      "file:///home/dev/project/src.py" in urls(out), str(urls(out)))

# 33. colored `git status` porcelain
out = t(GREEN + "M  src/app.py" + RST)
check("33 colored status wrapped",
      OSC + "file:///home/dev/project/src/app.py" + ST + "src/app.py" in out,
      repr(out))
check("33 colored status visible",
      visible(out) == "M  src/app.py\n", repr(visible(out)))

# 34. colored `git log --stat`
out = t(BOLD + " src/app.py | 4 ++--" + RST)
check("34 colored log stat wrapped",
      OSC + "file:///home/dev/project/src/app.py" + ST + "src/app.py" in out,
      repr(out))

# 35. colored grep output
out = t(CYAN + "src/app.py:42:    return foo()" + RST)
check("35 colored grep target",
      any(u.startswith("file:///home/dev/project/src/app.py") for u in urls(out)),
      str(urls(out)))
check("35 colored grep line fragment",
      any("#42" in u for u in urls(out)), str(urls(out)))

# 36. colored hunk header is passed through (no path to wrap)
outh = t(CYAN + "@@ -1 +1 @@" + RST)
check("36 colored hunk header unchanged",
      outh == CYAN + "@@ -1 +1 @@" + RST + "\n", repr(outh))

# 37. colored hunk content lines are passed through (with color)
for colored_line in (RED + "-old line" + RST,
                     GREEN + "+new line" + RST,
                     " context" + RST):
    o = transform(colored_line, ROOT, DEFAULT)
    check(f"37 unchanged: {colored_line!r}", o == colored_line, repr(o))

# 38. colored `--- /dev/null` is NOT wrapped
out = t(BOLD + "--- /dev/null" + RST)
check("38 colored /dev/null untouched",
      OSC not in out and out == BOLD + "--- /dev/null" + RST + "\n", repr(out))

# 39. multiple SGR codes between path and end (e.g. colored timestamp)
out = t(BOLD + "--- " + CYAN + "a/f.txt" + RST + "\ttimestamp" + RST)
check("39 multi-SGR path wrapped",
      OSC + "file:///home/dev/project/f.txt" + ST + "a/f.txt" in out,
      repr(out))
check("39 multi-SGR timestamp preserved",
      visible(out).endswith("a/f.txt\ttimestamp\n"), repr(visible(out)))


# CLI scenarios via subprocess
def run(args, stdin=""):
    env = os.environ.copy()
    env["HOME"] = TEST_HOME
    return subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "..", "taco.py"), *args],
        input=stdin, capture_output=True, text=True, env=env,
    )


# 21. help
r = run(["--help"])
check("21 exit 0", r.returncode == 0, str(r.returncode))
check("21 stdin/stdout", "stdin" in r.stdout and "stdout" in r.stdout, r.stdout)
check("21 template", "--template" in r.stdout, r.stdout)
check("21 root", "--root" in r.stdout, r.stdout)
check("21 pager", "--pager" in r.stdout and "--no-pager" in r.stdout, r.stdout)

# 22. empty input
r = run([], stdin="")
check("22 empty", r.stdout == "", repr(r.stdout))
check("22 exit 0", r.returncode == 0, str(r.returncode))

# 23. no recognisable path
inp = "Hello, world!\ntotally random text\n"
r = run(["--root", ROOT], stdin=inp)
check("23 passthrough", r.stdout == inp, repr(r.stdout))

# 20 via CLI
r = run(["--root", "/srv/code"], stdin="--- a/app.py\n")
check("20 cli target", "file:///srv/code/app.py" in r.stdout, repr(r.stdout))


# ----------------------------------------------------------------------
# Persistent config: preset flags, config file, env-var override
# ----------------------------------------------------------------------

# Reset config between scenarios by unlinking the file when present.
def reset_config():
    try:
        os.remove(CONFIG_PATH)
    except FileNotFoundError:
        pass


# 40. {file} and {path} placeholders render the same way
out_file = t("--- a/src/app.py", template="proto://{file}")
out_path = t("--- a/src/app.py", template="proto://{path}")
check("40 {file} matches {path}", urls(out_file) == urls(out_path),
      f"{urls(out_file)} != {urls(out_path)}")
check("40 {file} renders", "proto://home/dev/project/src/app.py" in urls(out_file),
      str(urls(out_file)))

# 41. --atom renders and saves to the config file
reset_config()
r = run(["--atom", "--root", ROOT], stdin="--- a/src/app.py\n")
check("41 atom exit 0", r.returncode == 0, str(r.returncode))
check("41 atom target", "atom://open?url=file:///home/dev/project/src/app.py&line=1"
       in r.stdout, repr(r.stdout))
check("41 config file exists", os.path.isfile(CONFIG_PATH), CONFIG_PATH)
with open(CONFIG_PATH) as f:
    saved = json.load(f)
check("41 config saved", saved == {
    "default_template": "atom://open?url=file:///{file}&line={line}"
}, repr(saved))

# 42. subsequent run without flags uses the saved default
r = run(["--root", ROOT], stdin="--- a/src/app.py\n")
check("42 reuses saved", "atom://open?url=file:///home/dev/project/src/app.py&line=1"
       in r.stdout, repr(r.stdout))

# 43. --pycharm-community preset
reset_config()
r = run(["--pycharm-community", "--root", ROOT], stdin="--- a/src/app.py\n")
check("43 pycharm-community target",
      "pycharm-community://open?url=file:///home/dev/project/src/app.py&line=1"
      in r.stdout, repr(r.stdout))
with open(CONFIG_PATH) as f:
    saved = json.load(f)
check("43 pycharm-community saved",
      saved["default_template"] ==
      "pycharm-community://open?url=file:///{file}&line={line}",
      repr(saved))

# 44. preset overwrites the previously stored default
reset_config()
run(["--atom", "--root", ROOT], stdin="")
run(["--code", "--root", ROOT], stdin="")
with open(CONFIG_PATH) as f:
    saved = json.load(f)
check("44 later preset wins", saved["default_template"] ==
      "code://open?url=file:///{file}&line={line}", repr(saved))

# 45. --template does NOT persist (one-off override)
reset_config()
r = run(["--template", "ephemeral://{file}", "--root", ROOT],
        stdin="--- a/src/app.py\n")
check("45 template applied", "ephemeral://home/dev/project/src/app.py" in r.stdout,
      repr(r.stdout))
check("45 template not saved", not os.path.isfile(CONFIG_PATH), CONFIG_PATH)

# 46. mutually exclusive: --template and --atom together is an error
r = run(["--template", "x://{file}", "--atom", "--root", ROOT], stdin="")
check("46 mutex --template/--atom", r.returncode != 0, str(r.returncode))
check("46 mutex error message",
      "not allowed" in (r.stderr or ""), r.stderr)

# 47. mutually exclusive: two presets together is an error
r = run(["--atom", "--code", "--root", ROOT], stdin="")
check("47 mutex two presets", r.returncode != 0, str(r.returncode))

# 48. malformed config falls back to the built-in default
reset_config()
with open(CONFIG_PATH, "w") as f:
    f.write("not json")
r = run(["--root", ROOT], stdin="--- a/src/app.py\n")
check("48 malformed stderr", "malformed" in (r.stderr or ""), r.stderr)
check("48 malformed fallback", "file:///home/dev/project/src/app.py" in r.stdout,
      repr(r.stdout))

# 49. config whose default_template is not a string falls back to default
reset_config()
with open(CONFIG_PATH, "w") as f:
    json.dump({"default_template": 42}, f)
r = run(["--root", ROOT], stdin="--- a/src/app.py\n")
check("49 non-string default", "file:///home/dev/project/src/app.py" in r.stdout,
      repr(r.stdout))

# 50. config that is valid JSON but not an object falls back to default
reset_config()
with open(CONFIG_PATH, "w") as f:
    f.write('"a string"')
r = run(["--root", ROOT], stdin="--- a/src/app.py\n")
check("50 non-object config", "file:///home/dev/project/src/app.py" in r.stdout,
      repr(r.stdout))

# 51. all 11 presets produce a valid URL with the right scheme
expected = {
    "atom":              "atom://open?url=file:///home/dev/project/src/app.py&line=1",
    "code":              "code://open?url=file:///home/dev/project/src/app.py&line=1",
    "emacs":             "emacs://open?url=file:///home/dev/project/src/app.py&line=1",
    "nano":              "nano://open?url=file:///home/dev/project/src/app.py&line=1",
    "phpstorm":          "phpstorm://open?url=file:///home/dev/project/src/app.py&line=1",
    "pycharm":           "pycharm://open?url=file:///home/dev/project/src/app.py&line=1",
    "pycharm-community": "pycharm-community://open?url=file:///home/dev/project/src/app.py&line=1",
    "subl":              "subl://open?url=file:///home/dev/project/src/app.py&line=1",
    "vim":               "vim://open?url=file:///home/dev/project/src/app.py&line=1",
    "webstorm":          "webstorm://open?url=file:///home/dev/project/src/app.py&line=1",
    "windsurf":          "windsurf://open?url=file:///home/dev/project/src/app.py&line=1",
}
for flag, expected_url in expected.items():
    reset_config()
    r = run([f"--{flag}", "--root", ROOT], stdin="--- a/src/app.py\n")
    check(f"51.{flag} exit 0", r.returncode == 0, str(r.returncode))
    check(f"51.{flag} target", expected_url in r.stdout, repr(r.stdout))
    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    check(f"51.{flag} saved", saved["default_template"] in taco.TemplateCatalog.PRESETS.values()
          and flag in saved["default_template"], repr(saved))

# 52. help lists every preset flag
r = run(["--help"])
for flag in expected:
    check(f"52.{flag} in help", f"--{flag}" in r.stdout, "missing in help")

# 53. ConfigStore unit checks
reset_config()
store = taco.ConfigStore(path=CONFIG_PATH)
check("53 load empty", store.load() == {}, repr(store.load()))
store.save(config={"default_template": "x://{file}"})
with open(CONFIG_PATH) as f:
    on_disk = json.load(f)
check("53 round trip", on_disk == {"default_template": "x://{file}"}, repr(on_disk))
check("53 load after save", store.load() == {"default_template": "x://{file}"},
      repr(store.load()))

# 54. TemplateResolver unit checks
def resolve_template(template, preset, config):
    return taco.TemplateResolver().resolve(
        template=template, preset=preset, config=config,
    )


config = {"default_template": "stored://{file}"}
check("54 stored used", resolve_template(None, None, config) == ("stored://{file}", False),
      repr(resolve_template(None, None, config)))
check("54 preset wins", resolve_template(None, "atom", config)[0].startswith("atom://"),
      repr(resolve_template(None, "atom", config)))
check("54 template wins", resolve_template("adhoc://{file}", None, config) ==
      ("adhoc://{file}", False), repr(resolve_template("adhoc://{file}", None, config)))
check("54 built-in default", resolve_template(None, None, {}) == (DEFAULT, False),
      repr(resolve_template(None, None, {})))

# 55. config file's stored default survives across invocations
reset_config()
run(["--subl", "--root", ROOT], stdin="")
r = run(["--root", ROOT], stdin="--- a/src/app.py\n")
check("55 subl persisted",
      "subl://open?url=file:///home/dev/project/src/app.py&line=1" in r.stdout,
      repr(r.stdout))

# 56. PRESETS module constant
check("56 PRESETS count", len(taco.TemplateCatalog.PRESETS) == 11, repr(taco.TemplateCatalog.PRESETS))
check("56 all use {file}",
      all("{file}" in v and "{line}" in v for v in taco.TemplateCatalog.PRESETS.values()),
      repr(taco.TemplateCatalog.PRESETS))


# ----------------------------------------------------------------------
# Hunk header linking: {line} comes from `new_start` in the @@ -X,Y +N,M @@
# header once a file has been established earlier in the stream.
# ----------------------------------------------------------------------

def t_state(*lines, root=ROOT, template=DEFAULT):
    state = taco.StreamState()
    return [transform(l, root, template, state) for l in lines]


# 57. hunk header after `diff --git` uses the b/ file at new_start + 3
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +5,7 @@\n",
)
check("57 hunk header wrapped", OSC in out[1], repr(out[1]))
check("57 hunk header target",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[1])))

# 58. hunk header after `--- a/` and `+++ b/` uses the b/ file;
# a newly created file (-0,0 +1,3) links at line 1
out = t_state(
    "--- a/src/app.py\n",
    "+++ b/src/app.py\n",
    "@@ -0,0 +1,3 @@\n",
)
check("58 hunk header uses b/ at line 1 for new file",
      urls(out[2]) == ["file:///home/dev/project/src/app.py#1"],
      str(urls(out[2])))

# 59. hunk header without any preceding file is passed through unchanged
out = t("@@ -1,3 +5,7 @@")
check("59 no OSC", OSC not in out, repr(out))
check("59 unchanged", out == "@@ -1,3 +5,7 @@\n", repr(out))

# 60. hunk header with new_start omitting the line count (`+N` not `+N,M`)
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1 +5 @@\n",
)
check("60 new_start without count", urls(out[1]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[1])))

# 61. hunk header followed by another hunk header picks up the latest new_start
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +5,7 @@\n",
    "@@ -20,2 +42,5 @@\n",
)
check("61 first hunk", urls(out[1]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[1])))
check("61 second hunk", urls(out[2]) == ["file:///home/dev/project/src/app.py#45"],
      str(urls(out[2])))

# 62. a new `diff --git` switches the current file for subsequent hunks
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +5,7 @@\n",
    "diff --git a/README.md b/README.md\n",
    "@@ -0,0 +1,2 @@\n",
)
check("62 first hunk file", urls(out[1]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[1])))
check("62 second hunk file (new file at line 1)", urls(out[3]) == ["file:///home/dev/project/README.md#1"],
      str(urls(out[3])))

# 63. hunk header visible text is preserved (hunk with function context)
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +5,7 @@ def foo():\n",
)
check("63 hunk with context wrapped", OSC in out[1], repr(out[1]))
check("63 hunk with context visible",
      visible(out[1]) == "@@ -1,3 +5,7 @@ def foo():\n",
      repr(visible(out[1])))

# 64. hunk header after `--- a/foo\n--- /dev/null` keeps the a/ file
out = t_state(
    "--- a/src/app.py\n",
    "--- /dev/null\n",
    "@@ -1,3 +5,7 @@\n",
)
check("64 /dev/null doesn't clear file",
      urls(out[2]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[2])))

# 65. hunk header with colored output preserves SGR and is linked
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    CYAN + "@@ -1,3 +5,7 @@" + RST + "\n",
)
check("65 colored hunk header wrapped", OSC in out[1], repr(out[1]))
check("65 colored hunk header target",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#8"],
      str(urls(out[1])))
check("65 colored hunk header preserves SGR",
      CYAN in out[1] and RST in out[1], repr(out[1]))

# 66. hunk header with custom template using {line} placeholder
tmpl = "pycharm-community://open?url=file:///{path}&line={line}"
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +5,7 @@\n",
    template=tmpl,
)
check("66 hunk header with {line} template",
      urls(out[1]) == ["pycharm-community://open?url=file:///home/dev/project/src/app.py&line=8"],
      str(urls(out[1])))

# 67. StreamState defaults: current_file None, current_line 1
s = taco.StreamState()
check("67 default current_file", s.current_file is None, repr(s.current_file))
check("67 default current_line", s.current_line == 1, repr(s.current_line))

# 68. transform_line without explicit state still works (backward compat)
out = t("--- a/src/app.py")
check("68 backward compat no state", OSC in out, repr(out))

# 69. file outside the repo leaves state.current_file None
out = t_state(
    "--- a/../../etc/passwd\n",
    "@@ -1,3 +5,7 @@\n",
)
check("69 hunk header passthrough on out-of-repo",
      OSC not in out[1] and out[1] == "@@ -1,3 +5,7 @@\n", repr(out[1]))

# 70. handle_hunk_header updates state.current_line for downstream consumers
s = taco.StreamState()
s.current_file = "/home/dev/project/src/app.py"
transform("@@ -1,3 +5,7 @@\n", ROOT, DEFAULT, s)
check("70 current_line updated", s.current_line == 8, repr(s.current_line))

# 71. newly created file (-0,0 +1,M) links at line 1, not line 4
out = t_state(
    "diff --git a/new.py b/new.py\n",
    "@@ -0,0 +1,5 @@\n",
)
check("71 created file at line 1",
      urls(out[1]) == ["file:///home/dev/project/new.py#1"],
      str(urls(out[1])))

# 72. modification at line 1 of an existing file links at line 1
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +1,4 @@\n",
)
check("72 modification at line 1",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#1"],
      str(urls(out[1])))

# 73. modification at line 2 links at line 2
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +2,5 @@\n",
)
check("73 modification at line 2",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#2"],
      str(urls(out[1])))

# 74. modification at line 3 (last "first-3-lines" boundary) links at line 3
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +3,6 @@\n",
)
check("74 modification at line 3",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#3"],
      str(urls(out[1])))

# 75. new_start == 4 (just past the first-3-lines threshold) uses +3 offset
out = t_state(
    "diff --git a/src/app.py b/src/app.py\n",
    "@@ -1,3 +4,5 @@\n",
)
check("75 new_start == 4 uses +3",
      urls(out[1]) == ["file:///home/dev/project/src/app.py#7"],
      str(urls(out[1])))


# ----------------------------------------------------------------------
# Broken pipe: `git show | taco | less` then quit the pager early.
# stdout.write raises BrokenPipeError; taco must exit 0 without a traceback.
# ----------------------------------------------------------------------

class _BrokenPipeOut:
    def write(self, data):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


# 76. transform_stream propagates BrokenPipeError from stdout.write
raised = False
try:
    transform_stream(["--- a/src/app.py\n"], _BrokenPipeOut(), ROOT, DEFAULT)
except BrokenPipeError:
    raised = True
check("76 transform_stream raises BrokenPipeError", raised)

# 77. CLI: closed stdout (early pager exit) -> exit 0, no traceback
env = os.environ.copy()
env["HOME"] = TEST_HOME
proc = subprocess.Popen(
    [sys.executable, os.path.join(os.path.dirname(__file__), "..", "taco.py"),
     "--root", ROOT],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
)
proc.stdout.close()
try:
    proc.stdin.write(b"--- a/src/app.py\n" * 10000)
    proc.stdin.close()
except (BrokenPipeError, ValueError):
    pass
proc.wait()
stderr = proc.stderr.read().decode()
check("77 broken pipe exit 0", proc.returncode == 0, str(proc.returncode))
check("77 no traceback on stderr",
      "BrokenPipeError" not in stderr and "Traceback" not in stderr,
      repr(stderr))


# ----------------------------------------------------------------------
# Pager: when stdout is a terminal, transformed output can be piped into
# `less` (or $TACO_PAGER / $PAGER / --pager).  A pipe or `--no-pager`
# must keep the old direct-write behaviour.
# ----------------------------------------------------------------------

def resolve_pager(requested=None, disabled=False, env=None, isatty=True):
    command = taco.PagerSelector(
        env=env if env is not None else {},
        is_terminal=isatty,
        which=lambda name: "/usr/bin/" + name,
    ).select(requested=requested, disabled=disabled)
    return None if command is None else command.argv


check("78 no tty -> no pager", resolve_pager(isatty=False) is None)

cmd = resolve_pager()
check("79 default is less", cmd is not None and cmd[0] == "less", repr(cmd))
check("79 less gets -R", cmd is not None and "-R" in cmd, repr(cmd))

cmd = resolve_pager(env={"TACO_PAGER": "cat", "PAGER": "more"})
check("80 TACO_PAGER wins", cmd == ["cat"], repr(cmd))

cmd = resolve_pager(env={"PAGER": "more"})
check("80 PAGER fallback", cmd == ["more"], repr(cmd))

cmd = resolve_pager(requested="less -F", env={"PAGER": "more"})
check("81 --pager wins", cmd == ["less", "-F", "-R"], repr(cmd))

cmd = resolve_pager(requested="less -R")
check("81 existing -R preserved", cmd == ["less", "-R"], repr(cmd))

check("82 --no-pager wins", resolve_pager(disabled=True) is None)


def run_pty(args, stdin_text, extra_env=None):
    master, slave = pty.openpty()
    env = os.environ.copy()
    env["HOME"] = TEST_HOME
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "..", "taco.py"), *args],
        stdin=subprocess.PIPE,
        stdout=slave,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    os.close(slave)
    try:
        proc.stdin.write(stdin_text)
        proc.stdin.close()
    except (BrokenPipeError, ValueError):
        pass
    chunks = []
    while True:
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    proc.wait()
    out = b"".join(chunks).decode(errors="replace")
    err = proc.stderr.read()
    proc.stderr.close()
    os.close(master)
    return out, err, proc.returncode


pager_script = os.path.join(TEST_HOME, "pager.sh")
with open(pager_script, "w") as f:
    f.write("#!/bin/sh\ncat\nprintf 'PAGER-RAN\\n'\n")
os.chmod(pager_script, 0o755)

# 83. a terminal + $PAGER -> pager runs and receives transformed output
out, err, rc = run_pty(
    ["--root", ROOT],
    "--- a/src/app.py\n",
    {"PAGER": pager_script, "TACO_PAGER": ""},
)
check("83 pager ran on tty", "PAGER-RAN" in out, repr(out))
check("83 pager got transformed output",
      "file:///home/dev/project/src/app.py" in out, repr(out))
check("83 pager exit 0", rc == 0, str(rc))
check("83 no stderr", err == "", repr(err))

# 84. --no-pager bypasses even a configured pager
out, err, rc = run_pty(
    ["--root", ROOT, "--no-pager"],
    "--- a/src/app.py\n",
    {"PAGER": pager_script},
)
check("84 no-pager skips pager", "PAGER-RAN" not in out, repr(out))
check("84 no-pager writes directly",
      "file:///home/dev/project/src/app.py" in out, repr(out))
check("84 no-pager exit 0", rc == 0, str(rc))

# 85. non-tty stdout is never paged, even with --pager
r = run(["--root", ROOT, "--pager", pager_script], stdin="--- a/src/app.py\n")
check("85 pipe skips pager", "PAGER-RAN" not in r.stdout, repr(r.stdout))
check("85 pipe still transforms",
      "file:///home/dev/project/src/app.py" in r.stdout, repr(r.stdout))

# 86. missing pager falls back to direct output with a warning
out, err, rc = run_pty(
    ["--root", ROOT, "--pager", "/nonexistent/taco-pager"],
    "--- a/src/app.py\n",
)
check("86 missing pager warning", "pager not found" in err, repr(err))
check("86 missing pager fallback",
      "file:///home/dev/project/src/app.py" in out, repr(out))
check("86 missing pager exit 0", rc == 0, str(rc))

# 87. --pager and --no-pager are mutually exclusive
r = run(["--pager", "cat", "--no-pager"], stdin="")
check("87 pager flags mutex", r.returncode != 0, str(r.returncode))

# 88. a pager that quits early is a clean exit, not a traceback
early_script = os.path.join(TEST_HOME, "early-pager.sh")
with open(early_script, "w") as f:
    f.write("#!/bin/sh\nhead -1 >/dev/null\n")
os.chmod(early_script, 0o755)
out, err, rc = run_pty(
    ["--root", ROOT],
    "--- a/src/app.py\n" * 10000,
    {"PAGER": early_script, "TACO_PAGER": ""},
)
check("88 early pager exit 0", rc == 0, str(rc))
check("88 early pager no traceback",
      "BrokenPipeError" not in err and "Traceback" not in err, repr(err))


# ----------------------------------------------------------------------
# Class-based API: the compatibility wrappers above delegate to these.
# ----------------------------------------------------------------------

resolver = taco.PathResolver(root=ROOT)
check("89 resolve inside root",
      resolver.resolve(path="src/app.py") == "/home/dev/project/src/app.py",
      repr(resolver.resolve(path="src/app.py")))
check("89 resolve escape", resolver.resolve(path="../../etc/passwd") is None)

urls_builder = taco.UrlTemplate(template="proto://{file}")
check("89 url fragment",
      urls_builder.build(abs_path="/home/dev/project/a.py", line=7) ==
      "proto://home/dev/project/a.py#7",
      repr(urls_builder.build(abs_path="/home/dev/project/a.py", line=7)))

transformer = taco.TransformerFactory().create(root=ROOT, template=DEFAULT)
out = transformer.transform_line(line="--- a/src/app.py\n")
check("89 transformer class", urls(out) == ["file:///home/dev/project/src/app.py"],
      repr(out))


reset_config()

print(f"\n{passed} passed, {failed} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("All scenarios verified.")

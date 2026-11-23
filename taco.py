#!/usr/bin/env python3
"""Taco - make file paths in terminal output clickable OSC 8 hyperlinks.

The tool reads stdin line by line, recognises the common line shapes
emitted by ``git``, ``diff`` and ``grep`` and wraps the file paths it
finds in OSC 8 escape sequences pointing at a configurable URL scheme.

Usage:
    something-that-prints-paths | taco [options]

When stdout is a terminal the output is piped through a pager (``less``
by default); use ``--no-pager`` to write directly or ``--pager CMD`` to
choose another pager.

A persistent default template can be stored in
``~/.config/TangoMan75/taco/config.json``::

    {
        "default_template": "atom://open?url=file:///{file}&line={line}"
    }

When a preset flag (``--atom``, ``--code``, ...) is used, the matching
template is written back to the config so the choice persists across
invocations.  ``--template`` is a one-off override and does not touch
the config.  ``{path}`` and ``{file}`` are interchangeable placeholders
for the absolute file path.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class Osc8Link:
    """Build OSC 8 terminal hyperlinks.

    The sequence is ``ESC ] 8 ; ; URL ST TEXT ESC ] 8 ; ; ST`` where ST
    is the string terminator ``ESC \\``.
    """

    OSC = "\x1b]8;;"
    ST = "\x1b\\"

    @classmethod
    def wrap(cls, *, text, url):
        """Return ``text`` wrapped in a hyperlink pointing at ``url``."""
        return f"{cls.OSC}{url}{cls.ST}{text}{cls.OSC}{cls.ST}"


class Ansi:
    """Helpers for the SGR sequences emitted by colored diff output."""

    SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
    PREFIX = r"(?:\x1b\[[0-9;]*m)*"

    @classmethod
    def anchored(cls, *, body):
        """Compile an entire-line pattern that tolerates SGR prefixes
        and suffixes around ``body``."""
        return re.compile(cls.PREFIX + body + cls.PREFIX + r"$")


class StreamState:
    """Per-stream state shared by line handlers.

    ``current_file`` is the absolute path most recently established by
    a file-bearing line.  ``current_line`` is the first modified line
    of the current hunk, derived from the hunk header's ``new_start``
    and the three context lines normally printed before a change.
    """

    def __init__(self):
        self.current_file = None
        self.current_line = 1

    def remember_file(self, *, path):
        """Remember the file subsequent context lines refer to."""
        self.current_file = path

    def reached_hunk(self, *, old_start, new_start):
        """Update ``current_line`` from hunk coordinates."""
        if old_start == 0 or new_start <= 3:
            self.current_line = new_start
        else:
            self.current_line = new_start + 3


class PathResolver:
    """Resolve repository-relative paths against a repository root."""

    def __init__(self, *, root):
        self._root = root

    def resolve(self, *, path):
        """Return the normalised absolute path, or ``None`` when the
        path escapes the repository root."""
        if self._root is None:
            return None
        abs_path = os.path.normpath(os.path.join(self._root, path))
        root_norm = os.path.normpath(self._root)
        if abs_path == root_norm or abs_path.startswith(root_norm + os.sep):
            return abs_path
        return None


class UrlTemplate:
    """Render editor URLs from a template.

    ``{path}`` and ``{file}`` are interchangeable placeholders for the
    absolute file path without its leading slash.  ``{line}`` is the
    line number, or ``1`` when unknown.  A template without ``{line}``
    receives a ``#line`` fragment when a line is known.
    """

    def __init__(self, *, template):
        self._template = template

    def build(self, *, abs_path, line=None):
        rel_path = abs_path.lstrip("/")
        values = {"path": rel_path, "file": rel_path}
        if "{line}" in self._template:
            values["line"] = line if line is not None else 1
            return self._template.format(**values)
        url = self._template.format(**values)
        if line is not None:
            return f"{url}#{line}"
        return url


class LineContext:
    """Collaborators and state available to a line handler."""

    def __init__(self, *, resolver, url_template, state):
        self._resolver = resolver
        self._url_template = url_template
        self._state = state

    def resolve(self, *, path):
        return self._resolver.resolve(path=path)

    def remember_file(self, *, path):
        self._state.remember_file(path=path)

    def url(self, *, abs_path, line=None):
        return self._url_template.build(abs_path=abs_path, line=line)

    @property
    def current_file(self):
        return self._state.current_file

    @property
    def current_line(self):
        return self._state.current_line

    def reached_hunk(self, *, old_start, new_start):
        self._state.reached_hunk(old_start=old_start, new_start=new_start)


class LineHandler(ABC):
    """Contract for a recogniser that transforms one line shape."""

    @abstractmethod
    def handle(self, *, line, context):
        """Return the transformed line, or ``None`` when unrecognised."""


class RegexHandler(LineHandler):
    """Base class for handlers that match a compiled line pattern."""

    PATTERN = None

    def __init__(self, *, pattern=None):
        self._pattern = pattern if pattern is not None else self.PATTERN

    def handle(self, *, line, context):
        match = self._pattern.match(line)
        if match is None:
            return None
        return self._apply(line=line, match=match, context=context)

    @abstractmethod
    def _apply(self, *, line, match, context):
        """Transform a matched line."""


class SinglePathHandler(RegexHandler):
    """Base class for handlers that wrap one path within a line.

    Subclasses select the capture group and may customise how the
    matched path is normalised or which URL is built.  ``CONSUME_ON_MISS``
    controls whether an unresolvable path returns the original line
    (stopping the handler chain) or ``None`` (letting later handlers
    inspect the line).
    """

    GROUP = 1
    CONSUME_ON_MISS = False

    def _accepts(self, *, match):
        return True

    def _path_from(self, *, spec, match):
        return spec

    def _url_for(self, *, context, abs_path, match):
        return context.url(abs_path=abs_path)

    def _apply(self, *, line, match, context):
        if not self._accepts(match=match):
            return None
        spec = match.group(self.GROUP)
        abs_path = context.resolve(path=self._path_from(spec=spec, match=match))
        if abs_path is None:
            return line if self.CONSUME_ON_MISS else None
        context.remember_file(path=abs_path)
        url = self._url_for(context=context, abs_path=abs_path, match=match)
        start, end = match.span(self.GROUP)
        return line[:start] + Osc8Link.wrap(text=spec, url=url) + line[end:]


class TwoPathHandler(RegexHandler):
    """Base class for lines that mention both an ``a/`` and ``b/`` path."""

    def _apply(self, *, line, match, context):
        a_path, b_path = match.group(1), match.group(2)
        output = line
        b_abs = None
        for display, path in (("a/" + a_path, a_path), ("b/" + b_path, b_path)):
            if path == "/dev/null":
                continue
            abs_path = context.resolve(path=path)
            if abs_path is None:
                continue
            if path == b_path:
                b_abs = abs_path
            link = Osc8Link.wrap(text=display, url=context.url(abs_path=abs_path))
            output = output.replace(display, link, 1)
        context.remember_file(path=b_abs)
        return output


class DiffGitHandler(TwoPathHandler):
    """Handle ``diff --git a/path b/path`` headers."""

    PATTERN = Ansi.anchored(body=r"diff --git a/(.+?) b/(.+?)")


class BinaryHandler(TwoPathHandler):
    """Handle ``Binary files a/path and b/path differ`` lines."""

    PATTERN = Ansi.anchored(body=r"Binary files a/(.+?) and b/(.+?) differ")


class OldNewHandler(SinglePathHandler):
    """Handle ``--- a/path`` and ``+++ b/path`` file headers."""

    CONSUME_ON_MISS = True

    def __init__(self, *, marker):
        super().__init__(
            pattern=re.compile(
                Ansi.PREFIX
                + re.escape(marker)
                + r" (?:\x1b\[[0-9;]*m)*([^\s\x1b]+?)"
                + r"(?:\x1b\[[0-9;]*m)*(\t.*)?$"
            )
        )

    def _path_from(self, *, spec, match):
        if spec.startswith(("a/", "b/")):
            return spec[2:]
        return spec


class RenameHandler(SinglePathHandler):
    """Handle ``rename from`` and ``rename to`` lines."""

    PATTERN = Ansi.anchored(body=r"rename (?:from|to) (.+?)")
    CONSUME_ON_MISS = True


class CopyHandler(SinglePathHandler):
    """Handle ``copy from`` and ``copy to`` lines."""

    PATTERN = Ansi.anchored(body=r"copy (?:from|to) (.+?)")
    CONSUME_ON_MISS = True


class LogStatHandler(SinglePathHandler):
    """Handle ``git log --stat`` file summary rows."""

    PATTERN = Ansi.anchored(body=r" (\S[^|]*?) \| \d+.*")

    def _path_from(self, *, spec, match):
        return spec.strip()


class StatusHandler(SinglePathHandler):
    """Handle ``git status --porcelain`` rows."""

    PATTERN = Ansi.anchored(body=r"([MADRC?! ]{2}) (.+?)")
    GROUP = 2

    def _accepts(self, *, match):
        return bool(match.group(1).strip())


class HunkHeaderHandler(RegexHandler):
    """Handle ``@@ -old +new @@`` hunk headers."""

    PATTERN = Ansi.anchored(body=r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@.*")

    def _apply(self, *, line, match, context):
        old_start = int(match.group(1))
        new_start = int(match.group(2))
        context.reached_hunk(old_start=old_start, new_start=new_start)
        if context.current_file is None:
            return line
        url = context.url(abs_path=context.current_file, line=context.current_line)
        suffix = "\n" if line.endswith("\n") else ""
        return Osc8Link.wrap(text=line.rstrip("\n"), url=url) + suffix


class HunkContentHandler(LineHandler):
    """Pass hunk content through without trying to link it."""

    def handle(self, *, line, context):
        if line[:1] in ("+", "-", " "):
            return line
        return None


class GrepHandler(SinglePathHandler):
    """Handle ``path:line: text`` output from grep and git grep."""

    PATTERN = Ansi.anchored(body=r"(\S+?):(\d+)(:.*)?")

    def _url_for(self, *, context, abs_path, match):
        return context.url(abs_path=abs_path, line=int(match.group(2)))


class BarePathHandler(LineHandler):
    """Handle output that is nothing but a file path."""

    PATTERN = re.compile(r"[\w./-]+")

    def handle(self, *, line, context):
        text = line.rstrip("\n")
        if text.startswith(("+", "-", " ")):
            return None
        if self.PATTERN.fullmatch(text) is None:
            return None
        if "." not in text and "/" not in text:
            return None
        abs_path = context.resolve(path=text)
        if abs_path is None:
            return None
        context.remember_file(path=abs_path)
        suffix = "\n" if line.endswith("\n") else ""
        return Osc8Link.wrap(text=text, url=context.url(abs_path=abs_path)) + suffix


class LineTransformer:
    """Apply an ordered collection of handlers to lines and streams."""

    def __init__(self, *, handlers, resolver, url_template):
        self._handlers = tuple(handlers)
        self._resolver = resolver
        self._url_template = url_template

    def transform_line(self, *, line, state=None):
        """Transform one line, using ``state`` when supplied."""
        if Osc8Link.OSC in line:
            return line
        if not line.strip():
            return line
        if state is None:
            state = StreamState()
        context = LineContext(
            resolver=self._resolver,
            url_template=self._url_template,
            state=state,
        )
        for handler in self._handlers:
            result = handler.handle(line=line, context=context)
            if result is not None:
                return result
        return line

    def transform_stream(self, *, stdin, stdout):
        """Transform a complete stream, threading one state through it."""
        state = StreamState()
        for line in stdin:
            stdout.write(self.transform_line(line=line, state=state))
        stdout.flush()


class TransformerFactory:
    """Compose the default handler chain for a repository root."""

    def create(self, *, root, template):
        return LineTransformer(
            handlers=(
                DiffGitHandler(),
                OldNewHandler(marker="---"),
                OldNewHandler(marker="+++"),
                BinaryHandler(),
                RenameHandler(),
                CopyHandler(),
                LogStatHandler(),
                StatusHandler(),
                HunkHeaderHandler(),
                HunkContentHandler(),
                GrepHandler(),
                BarePathHandler(),
            ),
            resolver=PathResolver(root=root),
            url_template=UrlTemplate(template=template),
        )


class GitRootFinder:
    """Locate the current Git repository root."""

    def find(self):
        """Return the git toplevel for the current directory, or ``None``."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return None


class Reporter(ABC):
    """Contract for non-fatal diagnostic messages."""

    PREFIX = "taco"

    @abstractmethod
    def warn(self, *, message):
        """Report a recoverable problem."""


class StderrReporter(Reporter):
    """Write diagnostics to a stream (stderr by default)."""

    def __init__(self, *, stream=None):
        self._stream = stream if stream is not None else sys.stderr

    def warn(self, *, message):
        print(f"{self.PREFIX}: {message}", file=self._stream)


class NullReporter(Reporter):
    """Reporter used when diagnostics are not wanted."""

    def warn(self, *, message):
        pass


class ConfigStore:
    """Load and save the persistent JSON configuration."""

    CONFIG_DIR = Path.home() / ".config" / "TangoMan75" / "taco"
    CONFIG_PATH = CONFIG_DIR / "config.json"

    def __init__(self, *, path=None, reporter=None):
        self._path = Path(path) if path is not None else self.CONFIG_PATH
        self._reporter = reporter if reporter is not None else NullReporter()

    def load(self):
        """Return the stored configuration, or ``{}`` when unavailable."""
        if not self._path.is_file():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            self._reporter.warn(
                message=f"ignoring malformed config {self._path}: {exc}"
            )
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def save(self, *, config):
        """Persist ``config``, creating parent directories as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as stream:
            json.dump(config, stream, indent=4)
            stream.write("\n")


class TemplateCatalog:
    """Built-in URL templates and editor presets."""

    DEFAULT = "file:///{path}"
    PRESETS = {
        "atom": "atom://open?url=file:///{file}&line={line}",
        "code": "code://open?url=file:///{file}&line={line}",
        "emacs": "emacs://open?url=file:///{file}&line={line}",
        "nano": "nano://open?url=file:///{file}&line={line}",
        "phpstorm": "phpstorm://open?url=file:///{file}&line={line}",
        "pycharm": "pycharm://open?url=file:///{file}&line={line}",
        "pycharm-community": "pycharm-community://open?url=file:///{file}&line={line}",
        "subl": "subl://open?url=file:///{file}&line={line}",
        "vim": "vim://open?url=file:///{file}&line={line}",
        "webstorm": "webstorm://open?url=file:///{file}&line={line}",
        "windsurf": "windsurf://open?url=file:///{file}&line={line}",
    }

    @classmethod
    def default(cls):
        return cls.DEFAULT

    @classmethod
    def preset(cls, *, name):
        return cls.PRESETS[name]


class TemplateResolver:
    """Select a template from CLI overrides, presets, or stored config."""

    def __init__(self, *, catalog=None):
        self._catalog = catalog if catalog is not None else TemplateCatalog

    def resolve(self, *, template, preset, config):
        """Return ``(template, persist)``.

        Precedence is ``--template``, then a preset flag, then the
        stored ``default_template``, then the built-in default.  Only a
        preset asks the caller to persist the choice.
        """
        if template:
            return template, False
        if preset:
            return self._catalog.preset(name=preset), True
        stored = config.get("default_template")
        if isinstance(stored, str) and stored:
            return stored, False
        return self._catalog.default(), False


class PagerCommand:
    """Validated pager command line."""

    def __init__(self, *, argv):
        if not argv:
            raise ValueError("pager command must not be empty")
        self._argv = tuple(argv)

    @property
    def argv(self):
        return list(self._argv)

    @property
    def executable(self):
        return self._argv[0]


class PagerSelector:
    """Choose a pager command from CLI options and environment."""

    DEFAULT = "less"
    ENV = "TACO_PAGER"
    RAW_FLAGS = ("-R", "-r", "--raw-control-chars")

    def __init__(self, *, env=None, is_terminal=None, which=None, reporter=None):
        self._env = env if env is not None else os.environ
        self._is_terminal = is_terminal
        self._which = which
        self._reporter = reporter if reporter is not None else NullReporter()

    def select(self, *, requested=None, disabled=False):
        """Return a :class:`PagerCommand`, or ``None`` for direct output."""
        if disabled:
            return None
        if not self._terminal():
            return None
        env = self._env
        explicit = bool(requested) or bool(env.get(self.ENV)) or bool(env.get("PAGER"))
        raw = requested or env.get(self.ENV) or env.get("PAGER") or self.DEFAULT
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            self._reporter.warn(message=f"invalid pager command {raw!r}: {exc}")
            return None
        if not argv:
            return None
        if not self._find(argv[0]):
            if explicit:
                self._reporter.warn(message=f"pager not found: {argv[0]}")
            return None
        if os.path.basename(argv[0]) == "less" and not self._has_raw_flag(argv[1:]):
            argv.append("-R")
        return PagerCommand(argv=argv)

    def _terminal(self):
        if self._is_terminal is None:
            return sys.stdout.isatty()
        if callable(self._is_terminal):
            return self._is_terminal()
        return self._is_terminal

    def _find(self, executable):
        which = self._which if self._which is not None else shutil.which
        return which(executable)

    def _has_raw_flag(self, args):
        for arg in args:
            if arg in self.RAW_FLAGS:
                return True
            if arg.startswith("-") and not arg.startswith("--") and ("R" in arg or "r" in arg):
                return True
        return False


class PagerRunner:
    """Feed transformed output to a pager process."""

    LESS_DEFAULT = "FRX"

    def __init__(self, *, transformer, reporter=None, env=None):
        self._transformer = transformer
        self._reporter = reporter if reporter is not None else NullReporter()
        self._env = env if env is not None else os.environ

    def run(self, *, command, stdin, stdout):
        """Run ``command`` and return the process exit code."""
        env = dict(self._env)
        if os.path.basename(command.executable) == "less" and "LESS" not in env:
            env["LESS"] = self.LESS_DEFAULT
        try:
            pager = subprocess.Popen(
                command.argv,
                stdin=subprocess.PIPE,
                stdout=stdout,
                text=True,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            self._reporter.warn(
                message=f"failed to start pager {command.executable}: {exc}"
            )
            try:
                self._transformer.transform_stream(stdin=stdin, stdout=stdout)
            except BrokenPipeError:
                pass
            return 0
        try:
            self._transformer.transform_stream(stdin=stdin, stdout=pager.stdin)
        except BrokenPipeError:
            pass
        except KeyboardInterrupt:
            self._stop(pager=pager)
            return 130
        finally:
            try:
                pager.stdin.close()
            except BrokenPipeError:
                pass
        try:
            pager.wait()
        except KeyboardInterrupt:
            self._stop(pager=pager)
            return 130
        return 0

    def _stop(self, *, pager):
        try:
            pager.terminate()
        except OSError:
            pass
        try:
            pager.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                pager.kill()
            except OSError:
                pass
            pager.wait()


class ArgumentParserBuilder:
    """Build the taco command-line parser."""

    def __init__(self, *, config_path):
        self._config_path = config_path

    def build(self):
        parser = argparse.ArgumentParser(
            prog="taco",
            description=(
                "Make file paths in terminal output clickable OSC 8 hyperlinks. "
                "Reads stdin, writes stdout."
            ),
            epilog=(
                "Preset flags persist their template to "
                f"{self._config_path} so the choice survives across invocations."
            ),
        )
        template_group = parser.add_mutually_exclusive_group()
        template_group.add_argument(
            "--template",
            default=None,
            metavar="URL",
            help="URL template with {path}/{file} and optional {line} "
                 "placeholders (one-off override, not persisted)",
        )
        for name, template in TemplateCatalog.PRESETS.items():
            template_group.add_argument(
                f"--{name}",
                action="store_const",
                const=name,
                dest="preset",
                help=f"open files in {name} using {template} (persists as default)",
            )
        parser.add_argument(
            "--root",
            default=None,
            metavar="PATH",
            help="repository root path (default: autodetect via git rev-parse)",
        )
        pager_group = parser.add_mutually_exclusive_group()
        pager_group.add_argument(
            "--pager",
            default=None,
            metavar="CMD",
            help="pager command used when stdout is a terminal "
                 "(default: $TACO_PAGER, $PAGER, or less)",
        )
        pager_group.add_argument(
            "--no-pager",
            action="store_true",
            help="write directly to stdout instead of paging",
        )
        return parser


class Application:
    """Command-line entry point: parse, configure, and run the filter."""

    def __init__(
        self,
        *,
        argv=None,
        stdin=None,
        stdout=None,
        stderr=None,
        env=None,
        config_path=None,
        transformer_factory=None,
    ):
        self._argv = argv
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stdout = stdout if stdout is not None else sys.stdout
        self._stderr = stderr if stderr is not None else sys.stderr
        self._env = env if env is not None else os.environ
        self._config_path = (
            config_path if config_path is not None else ConfigStore.CONFIG_PATH
        )
        self._transformer_factory = (
            transformer_factory
            if transformer_factory is not None
            else TransformerFactory()
        )
        self._reporter = StderrReporter(stream=self._stderr)

    def run(self):
        args = self._parse_args()
        config = self._load_config()
        template, persist = TemplateResolver().resolve(
            template=args.template,
            preset=args.preset,
            config=config,
        )
        if persist:
            self._persist_template(config=config, template=template)
        root = args.root or GitRootFinder().find() or os.getcwd()
        transformer = self._transformer_factory.create(root=root, template=template)
        pager = PagerSelector(
            env=self._env,
            is_terminal=self._stdout.isatty,
            reporter=self._reporter,
        ).select(requested=args.pager, disabled=args.no_pager)
        if pager is not None:
            runner = PagerRunner(
                transformer=transformer,
                reporter=self._reporter,
                env=self._env,
            )
            return runner.run(command=pager, stdin=self._stdin, stdout=self._stdout)
        return self._write_direct(transformer=transformer)

    def _parse_args(self):
        parser = ArgumentParserBuilder(config_path=self._config_path).build()
        return parser.parse_args(self._argv)

    def _load_config(self):
        return ConfigStore(
            path=self._config_path,
            reporter=self._reporter,
        ).load()

    def _persist_template(self, *, config, template):
        updated = dict(config)
        updated["default_template"] = template
        store = ConfigStore(path=self._config_path, reporter=self._reporter)
        try:
            store.save(config=updated)
        except OSError as exc:
            self._reporter.warn(message=f"failed to save config: {exc}")

    def _write_direct(self, *, transformer):
        try:
            transformer.transform_stream(stdin=self._stdin, stdout=self._stdout)
        except BrokenPipeError:
            self._silence_stdout()
            return 0
        except KeyboardInterrupt:
            return 130
        return 0

    def _silence_stdout(self):
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, self._stdout.fileno())
        except (AttributeError, OSError, ValueError):
            pass


if __name__ == "__main__":
    sys.exit(Application().run())

Feature: Taco - Clickable file paths in terminal output
  As a developer who lives in the terminal
  I want to pipe the output of git, diff, and grep through a filter
  So that file paths become clickable OSC 8 hyperlinks that open in my editor

  The tool reads stdin line by line, detects known line shapes from
  `git`, `diff` and `grep` output, and wraps the file paths it finds
  in OSC 8 escape sequences pointing at a configurable URL scheme.

  Background:
    Given a git repository rooted at "/home/dev/project"
    And a working directory inside that repository
    And the file "src/app.py" exists in the repository
    And the file "README.md" exists in the repository

  # ------------------------------------------------------------------
  # Default behaviour: file:// scheme
  # ------------------------------------------------------------------

  Scenario: Transform a `git diff` header line
    Given stdin contains the line:
      """
      diff --git a/src/app.py b/src/app.py
      """
    When taco is run with no extra arguments
    Then stdout should contain the OSC 8 escape sequence
    And the link target should be "file:///home/dev/project/src/app.py"
    And the visible text should still read "diff --git a/src/app.py b/src/app.py"

  Scenario: Transform a `--- a/path` line
    Given stdin contains the line:
      """
      --- a/src/app.py
      """
    When taco is run with no extra arguments
    Then the displayed "a/src/app.py" should be wrapped in a clickable link
    And the link target should be "file:///home/dev/project/src/app.py"

  Scenario: Transform a `+++ b/path` line
    Given stdin contains the line:
      """
      +++ b/src/app.py
      """
    When taco is run with no extra arguments
    Then the displayed "b/src/app.py" should be wrapped in a clickable link
    And the link target should be "file:///home/dev/project/src/app.py"

  Scenario: Transform both sides of a `git diff` line independently
    Given stdin contains the line:
      """
      diff --git a/old.py b/new.py
      """
    When taco is run with no extra arguments
    Then "a/old.py" should link to "file:///home/dev/project/old.py"
    And "b/new.py" should link to "file:///home/dev/project/new.py"

  # ------------------------------------------------------------------
  # diff command (non-git)
  # ------------------------------------------------------------------

  Scenario: Transform plain `diff -u` output
    Given stdin contains:
      """
      --- a.txt	2024-01-01 10:00:00.000000000 +0100
      +++ b.txt	2024-01-01 10:00:00.000000000 +0100
      @@ -1 +1 @@
      -foo
      +bar
      """
    When taco is run with no extra arguments
    Then the "a.txt" in the "---" line should link to "file:///home/dev/project/a.txt"
    And the "b.txt" in the "+++" line should link to "file:///home/dev/project/b.txt"
    And the hunk header "@@ -1 +1 @@" should be passed through unchanged

  # ------------------------------------------------------------------
  # /dev/null must never be transformed
  # ------------------------------------------------------------------

  Scenario: Leave /dev/null alone
    Given stdin contains:
      """
      --- a/src/app.py
      +++ /dev/null
      """
    When taco is run with no extra arguments
    Then "a/src/app.py" should be wrapped in a link
    And "/dev/null" should NOT be wrapped in a link

  # ------------------------------------------------------------------
  # Files outside the repository must not be transformed
  # ------------------------------------------------------------------

  Scenario: Leave paths outside the repository alone
    Given stdin contains the line:
      """
      --- a/../../etc/passwd
      """
    When taco is run with no extra arguments
    Then no OSC 8 escape sequence should be emitted
    And the line should be written to stdout unchanged

  # ------------------------------------------------------------------
  # grep output
  # ------------------------------------------------------------------

  Scenario: Transform `grep -n` output
    Given stdin contains the line:
      """
      src/app.py:42:    return foo()
      """
    When taco is run with no extra arguments
    Then the link target should be "file:///home/dev/project/src/app.py"
    And the link should include a line fragment that resolves to line 42

  Scenario: Transform `git grep -n` output
    Given stdin contains the line:
      """
      src/app.py:42:    return foo()
      """
    When taco is run with no extra arguments
    Then the visible text should remain "src/app.py:42:    return foo()"
    And the link target should be "file:///home/dev/project/src/app.py"

  # ------------------------------------------------------------------
  # git log / git show - file lists
  # ------------------------------------------------------------------

  Scenario: Transform `git log --stat` file list
    Given stdin contains the line:
      """
       src/app.py | 4 ++--
      """
    When taco is run with no extra arguments
    Then the "src/app.py" token should be wrapped in a clickable link

  Scenario: Transform `git status` porcelain output
    Given stdin contains the line:
      """
      M  src/app.py
      """
    When taco is run with no extra arguments
    Then the "src/app.py" token should be wrapped in a clickable link

  Scenario: Transform `git show --name-only` file list
    Given stdin contains the line:
      """
      src/app.py
      """
    When taco is run with no extra arguments
    Then the line should be wrapped in a clickable link to "file:///home/dev/project/src/app.py"

  # ------------------------------------------------------------------
  # Binary / rename / copy lines
  # ------------------------------------------------------------------

  Scenario: Transform rename lines
    Given stdin contains:
      """
      rename from old/name.py
      rename to new/name.py
      """
    When taco is run with no extra arguments
    Then "old/name.py" should link to "file:///home/dev/project/old/name.py"
    And "new/name.py" should link to "file:///home/dev/project/new/name.py"

  Scenario: Transform copy lines
    Given stdin contains:
      """
      copy from src.py
      copy to dst.py
      """
    When taco is run with no extra arguments
    Then "src.py" should link to "file:///home/dev/project/src.py"
    And "dst.py" should link to "file:///home/dev/project/dst.py"

  Scenario: Transform binary file diff marker
    Given stdin contains the line:
      """
      Binary files a/img.png and b/img.png differ
      """
    When taco is run with no extra arguments
    Then "a/img.png" should link to "file:///home/dev/project/img.png"
    And "b/img.png" should link to "file:///home/dev/project/img.png"

  # ------------------------------------------------------------------
  # Non-path content is passed through untouched
  # ------------------------------------------------------------------

  Scenario: Pass commit metadata through unchanged
    Given stdin contains:
      """
      commit efd941c9d07aa5e555e38f0c1d0662132c52d1b0 (HEAD -> main)
      Author: Matthias Morin <mat@tangoman.io>
      Date:   Mon Jun 22 19:03:22 2026 +0200
      """
    When taco is run with no extra arguments
    Then stdout should be byte-for-byte identical to stdin

  Scenario: Pass hunk content lines through unchanged
    Given stdin contains:
      """
      @@ -0,0 +1,3 @@
      +#!/usr/bin/env python3
      +
      +def main():
      """
    When taco is run with no extra arguments
    Then the hunk header should be passed through unchanged
    And the content lines beginning with " " or "+" or "-" should be passed through unchanged

  Scenario: Transform a hunk header into a clickable link using new_start
    Given stdin contains:
      """
      diff --git a/src/app.py b/src/app.py
      --- a/src/app.py
      +++ b/src/app.py
      @@ -1,3 +5,7 @@
      """
    When taco is run with no extra arguments
    Then "@@ -1,3 +5,7 @@" should link to "file:///home/dev/project/src/app.py#8"

  Scenario: A bare hunk header without a preceding file is not transformed
    Given stdin contains the line:
      """
      @@ -1,3 +5,7 @@
      """
    When taco is run with no extra arguments
    Then no OSC 8 escape sequence should be emitted
    And the line should be written to stdout unchanged

  Scenario: A hunk header after `rename to` links to the renamed file
    Given stdin contains:
      """
      diff --git a/old/name.py b/new/name.py
      rename from old/name.py
      rename to new/name.py
      @@ -1,3 +5,7 @@
      """
    When taco is run with no extra arguments
    Then "@@ -1,3 +5,7 @@" should link to "file:///home/dev/project/new/name.py#8"

  # ------------------------------------------------------------------
  # Custom URL scheme (third party handler)
  # ------------------------------------------------------------------

  Scenario: Use a custom URL scheme with line numbers
    Given taco is invoked with "--template 'pycharm-community://open?url=file:///{path}&line={line}'"
    And stdin contains:
      """
      diff --git a/src/app.py b/src/app.py
      --- a/src/app.py
      +++ b/src/app.py
      """
    When the input is processed
    Then the link targets should start with "pycharm-community://open?url=file:///"
    And the link targets should contain "&line=1"

  Scenario: Custom scheme without a line placeholder
    Given taco is invoked with "--template 'vscode://file/{path}:1'"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the link target should be "vscode://file/home/dev/project/src/app.py:1"

  # ------------------------------------------------------------------
  # CLI configuration
  # ------------------------------------------------------------------

  Scenario: Explicitly set the repository root
    Given taco is invoked with "--root /srv/code"
    And stdin contains the line:
      """
      --- a/app.py
      """
    When the input is processed
    Then the link target should be "file:///srv/code/app.py"

  Scenario: Show help
    Given taco is invoked with "--help"
    When the help is shown
    Then the output should describe the stdin/stdout usage
    And the output should list the "--template" option
    And the output should list the "--root" option

  # ------------------------------------------------------------------
  # Robustness
  # ------------------------------------------------------------------

  Scenario: Empty input
    Given stdin is empty
    When taco is run
    Then stdout should be empty
    And the process should exit with code 0

  Scenario: Input that has no recognisable path is passed through
    Given stdin contains:
      """
      Hello, world!
      totally random text
      """
    When taco is run with no extra arguments
    Then stdout should be byte-for-byte identical to stdin

  Scenario: Path that is too short to be a real file is not transformed
    Given stdin contains the line:
      """
      --- a/a
      """
    When taco is run with no extra arguments
    Then the line should still be transformed (single-character names are valid)
    And the link target should be "file:///home/dev/project/a"

  Scenario: Idempotency - running taco twice yields the same output
    Given stdin contains the line:
      """
      --- a/src/app.py
      """
    When taco is run twice in a pipeline
    Then the second run should detect the existing OSC 8 sequence
    And the line should be transformed exactly once

  # ------------------------------------------------------------------
  # Editor preset flags (--atom, --code, --vim, ...)
  # ------------------------------------------------------------------

  Scenario: The --atom preset renders atom:// links
    Given taco is invoked with "--atom"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the link targets should start with "atom://open?url=file:///"
    And the link targets should contain "&line=1"

  Scenario: The --code preset renders code:// links
    Given taco is invoked with "--code"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the link targets should start with "code://open?url=file:///"
    And the link targets should contain "&line=1"

  Scenario: The --pycharm-community preset renders pycharm-community:// links
    Given taco is invoked with "--pycharm-community"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the link targets should start with "pycharm-community://open?url=file:///"
    And the link targets should contain "&line=1"

  Scenario: The --vim preset renders vim:// links
    Given taco is invoked with "--vim"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the link targets should start with "vim://open?url=file:///"
    And the link targets should contain "&line=1"

  # ------------------------------------------------------------------
  # Persistent config
  # ------------------------------------------------------------------

  Scenario: A preset flag writes its template to the config file
    Given taco is invoked with "--atom"
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the config file should exist
    And the stored default template should be "atom://open?url=file:///{file}&line={line}"

  Scenario: A later preset flag overwrites the stored default
    Given taco is invoked with "--atom"
    And stdin is empty
    When the input is processed
    Given taco is invoked with "--code"
    And stdin is empty
    When the input is processed
    Then the config file should exist
    And the stored default template should be "code://open?url=file:///{file}&line={line}"

  Scenario: --template is a one-off override and does not persist
    Given taco is invoked with "--template ephemeral://{file}"
    And stdin is empty
    When the input is processed
    Then the config file should not exist

  Scenario: Stored default is used on subsequent runs without flags
    Given taco is invoked with "--atom"
    And stdin is empty
    When the input is processed
    Given taco is invoked with no extra arguments
    And stdin contains the line:
      """
      --- a/src/app.py
      """
    When the input is processed
    Then the persisted config should be used to render links

  Scenario: Preset flag and --template are mutually exclusive
    Given stdin is empty
    When running "--template x://{file} --atom" should fail with a usage error

  Scenario: Two preset flags are mutually exclusive
    Given stdin is empty
    When running "--atom --code" should fail with a usage error

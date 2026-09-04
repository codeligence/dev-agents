"""Read-only permission handler for the Claude Agent SDK.

Uses ``shlex`` (stdlib) to tokenise Bash commands, then applies a
default-deny allowlist.  Blocks command/process substitution, output
redirects, and any command not explicitly allowlisted.

Threat model — read this before extending the module
----------------------------------------------------

This handler protects against **mistakes**: an agent that, given a vague
or badly worded prompt, reaches for ``rm``, ``sed -i``, ``git checkout``,
an output redirect, or wanders into ``../other-project`` while researching.
Every rule here is written to stop a well-meaning agent from writing to
the filesystem or reading outside the repository it was pointed at.

It does **not** hold against an adversary.  A shell-token allowlist cannot
be a security boundary: bash expands globs, braces and ANSI-C quoting
after we have looked at the tokens, a symlink committed to the repository
resolves wherever its author chose, and the allowlisted git subcommands
share a large option surface with mutating ones.  Anyone who can plant
content in the analysed repository, or steer the prompt through an issue
or pull-request description, should be assumed able to read files the
service user can read.  Defending against that requires an OS-level
sandbox around the CLI process (read-only mount of the repository, no
inherited secrets, restricted network) or replacing Bash with narrowly
constructed tools that build ``argv`` without a shell.  Neither is done
here; do not extend this module in the belief that it is.

Within that model, read-only is only half the policy: every path the
subagent touches should also stay inside the repository it was pointed
at, so an accidental ``cat ../other-checkout/.env`` is refused rather than
echoed into a chat reply.  Both the Bash allowlist and the file tools are
therefore confined to *root*, the repository path the subagent runs
against.

Commands are classified into three tiers:

- **Tier 1 — Inherently read-only**: Commands that cannot write to the
  filesystem regardless of flags (e.g. ``ls``, ``cat``, ``grep``).
  Allowed with any arguments.
- **Tier 2 — Conditionally read-only**: Commands that are read-only by
  default but have specific write-enabling flags (e.g. ``sort -o``,
  ``find -exec``).  Blocked only when those flags appear.
- **Tier 3 — Complex (git)**: Requires subcommand-level validation.
  Top-level options that inject configuration or executables (``-c``,
  ``--config-env``, ``--exec-path``, ``--paginate``) are blocked
  unconditionally; each subcommand is classified as fully read-only,
  read-only with restrictions, or dual-mode (list vs. create).

Permission evaluation order (from SDK docs):
    Hooks -> Deny rules -> Permission mode -> Allow rules -> canUseTool callback
"""

from pathlib import Path
from typing import Any
import re
import shlex

from claude_agent_sdk.types import (
    CanUseTool,
    HookContext,
    HookInput,
    PermissionResultAllow,
    PermissionResultDeny,
    SyncHookJSONOutput,
    ToolPermissionContext,
)

from core.log import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — Tiered command safety model
# ---------------------------------------------------------------------------

# Tier 1: Inherently read-only commands — no flags can cause filesystem writes.
# Verified via manpages: none of these have any write-to-file flag.
TIER1_INHERENTLY_READONLY = frozenset(
    {"ls", "cat", "head", "tail", "wc", "grep", "rg", "uniq", "pwd"}
)

# Tier 2: Conditionally read-only commands — block specific write-enabling flags.
# Mapping of command -> frozenset of flags that enable file writes.
TIER2_WRITE_FLAGS: dict[str, frozenset[str]] = {
    "sort": frozenset({"-o", "--output"}),
    "tree": frozenset({"-o", "--output"}),
    "find": frozenset(
        {
            "-exec",
            "-execdir",
            "-delete",
            "-ok",
            "-okdir",
            "-fprint",
            "-fprint0",
            "-fls",
            "-fprintf",
        }
    ),
}

# Tier 3 — Git constants

# Git subcommands that are truly read-only — any flags are safe.
GIT_READONLY_SUBCOMMANDS = frozenset({"status", "ls-files", "rev-parse", "grep"})

# ``git grep -O``/``--open-files-in-pager`` runs the named program over the
# matching files, which is arbitrary command execution wearing a read-only
# subcommand's clothes.
GIT_GREP_PAGER_FLAGS = frozenset({"-O", "--open-files-in-pager"})

# Git subcommands that render diffs. ``log`` and ``show`` accept the full
# ``git diff`` option surface, so the three share one guard: ``--output``
# writes the rendered result to a file (``git log --output=notes.txt`` is an
# easy mistake for an agent asked to "save the history"), and ``--ext-diff``
# / ``--textconv`` hand the blobs to whatever program the repository's diff
# driver configuration names.
GIT_DIFF_RENDERING_SUBCOMMANDS = frozenset({"diff", "log", "show"})
GIT_DIFF_WRITE_FLAGS = frozenset({"--output"})
GIT_DIFF_EXEC_FLAGS = frozenset({"--ext-diff", "--textconv"})

# Git dual-mode subcommands: read-only when listing, mutating when creating.
# Detected by checking for mutating flags AND positional (non-flag) args.
GIT_DUAL_MODE_SUBCOMMANDS = frozenset({"branch", "tag"})

# Mutating flags for ``git branch`` (all forms that create, rename, delete, or
# modify tracking configuration).
GIT_BRANCH_MUTATING_FLAGS = frozenset(
    {
        "-d",
        "-D",
        "--delete",
        "-m",
        "-M",
        "--move",
        "-c",
        "-C",
        "--copy",
        "--edit-description",
        "-u",
        "--set-upstream-to",
        "--unset-upstream",
    }
)

# Branch flags that consume the next argument (so it's not a positional arg).
GIT_BRANCH_FLAGS_WITH_VALUE = frozenset(
    {
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
        "--sort",
        "--format",
        "-u",
        "--set-upstream-to",
    }
)

# Mutating flags for ``git tag`` (create, delete, sign, force).
GIT_TAG_MUTATING_FLAGS = frozenset(
    {"-d", "--delete", "-a", "--annotate", "-s", "--sign", "-f", "--force"}
)

# Tag flags that consume the next argument.
GIT_TAG_FLAGS_WITH_VALUE = frozenset(
    {
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
        "--sort",
        "--format",
        "-l",
        "--list",
    }
)

# Safe sub-subcommands for ``git remote`` (read-only operations).
GIT_REMOTE_SAFE_SUBCOMMANDS = frozenset({"show", "get-url"})

# Mutating sub-subcommands for ``git remote``.
GIT_REMOTE_MUTATING_SUBCOMMANDS = frozenset(
    {"add", "remove", "rm", "rename", "set-url", "prune", "set-head", "set-branches"}
)

# Git top-level flags that skip one value argument.
GIT_FLAGS_WITH_VALUE = frozenset({"-C", "--git-dir", "--work-tree"})

# Git top-level options that are refused outright. ``-c`` and
# ``--config-env`` inject arbitrary configuration (``core.pager``,
# ``diff.external``, …) for the one invocation; ``--exec-path`` makes git run
# its helper programs from a caller-chosen directory; ``--paginate`` forces
# the configured pager to be spawned even without a terminal.
GIT_BLOCKED_TOP_LEVEL_OPTIONS = frozenset(
    {"-c", "--config-env", "--exec-path", "-p", "--paginate"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_git_subcommand(args: list[str]) -> str | None:
    """Extract the git subcommand, skipping flags like ``-C <path>``.

    Stops at any option in :data:`GIT_BLOCKED_TOP_LEVEL_OPTIONS` and
    returns ``None`` so the caller can reject the entire command.

    Args:
        args: The argument list *after* the ``git`` token itself.

    Returns:
        The first positional argument (i.e. the subcommand), or ``None``.
    """
    i = 0
    while i < len(args):
        word = args[i]
        # ``--config-env=key=VAR`` and ``--exec-path=/dir`` carry their value
        # inline; compare on the option name alone.
        option = word.split("=", 1)[0] if word.startswith("--") else word
        if option in GIT_BLOCKED_TOP_LEVEL_OPTIONS:
            return None
        if word in GIT_FLAGS_WITH_VALUE:
            i += 2  # Skip flag and its value
            continue
        if word.startswith("-"):
            i += 1
            continue
        return word
    return None


# A ``$`` that starts a parameter expansion (``$HOME``, ``${HOME}``) rather
# than a literal dollar sign at the end of a regex.
_VARIABLE_EXPANSION = re.compile(r"\$[A-Za-z_{]")


def _is_path_like(value: str) -> bool:
    """Whether *value* looks like it addresses a location outside ``root``.

    Only escaping forms qualify: absolute paths, ``~`` expansions, and any
    use of ``..``.  Used to decide whether a Grep/Glob ``pattern`` is a
    location rather than a bare regex; git revisions such as ``HEAD~1`` or
    ``main..HEAD`` deliberately do not match.
    """
    if not value:
        return False
    if value.startswith(("/", "~")):
        return True
    return (
        value == ".."
        or value.startswith("../")
        or "/../" in value
        or value.endswith("/..")
    )


def _is_within(root: Path, value: str) -> bool:
    """Whether *value* resolves to *root* itself or something beneath it.

    ``resolve()`` collapses ``..`` segments and follows symlinks, so a
    relative name that happens to be a symlink is judged by where it points.
    That catches the accidental case (``cat creds`` where ``creds`` links
    elsewhere); it is not an adversarial guarantee — see the module
    docstring.
    """
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        root_resolved = root.resolve()
    except OSError:
        return False
    return resolved == root_resolved or root_resolved in resolved.parents


def _validate_paths(root: Path, args: list[str]) -> str | None:
    """Reject any argument that resolves outside *root*.

    Every non-option argument is resolved, not only those that look like an
    escape: a plain name such as ``creds`` is a path too, and if it is a
    symlink its target decides.  ``--flag=value`` forms are unpacked so the
    value is checked rather than the whole token; bare option names (``-r``,
    ``--stat``) are skipped.  Non-path arguments — git revisions, regexes,
    numbers — resolve to a (non-existent) location under *root* and pass.

    Relative paths are resolved against *root* rather than the shell's actual
    working directory: commands are validated one at a time with no memory of
    a preceding ``cd``, so ``cat ../x`` is refused even when it would have
    stayed inside the repository. Fail-closed is the right trade here — the
    agent can always use a repo-relative path.
    """
    for arg in args:
        if arg.startswith("-"):
            if "=" not in arg:
                continue
            value = arg.split("=", 1)[1]
        else:
            value = arg
        if not value or value == "--":
            continue
        if not _is_within(root, value):
            return f"Path outside the repository not allowed: {value}"
    return None


def _has_positional_args(
    args: list[str], subcmd: str, flags_with_value: frozenset[str]
) -> bool:
    """Check whether there are non-flag positional args after *subcmd*.

    Args:
        args: Full git argument list (after ``git``).
        subcmd: The subcommand to look past (e.g. ``"branch"``).
        flags_with_value: Flags that consume the next token as their value.

    Returns:
        ``True`` if a positional (non-flag) argument is found after *subcmd*.
    """
    past_subcmd = False
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if not past_subcmd:
            if arg == subcmd:
                past_subcmd = True
            continue
        # After the subcommand: classify each token
        if arg.startswith("-"):
            if arg in flags_with_value:
                skip_next = True
            continue
        # Non-flag token found — this is a positional arg (e.g. branch name)
        return True
    return False


# ---------------------------------------------------------------------------
# Token-based command validation (shlex)
# ---------------------------------------------------------------------------

# Operators that separate independent commands in a token stream. ``|&`` is
# bash's "pipe stdout+stderr" form and separates commands just like ``|``.
_COMMAND_SEPARATORS = frozenset({"|", "||", "&&", ";", "&", "|&"})

# Input redirects. They consume a *filename*, not a command, so the operand
# stays with the current (already validated) command.
_INPUT_REDIRECTS = frozenset({"<", "<<", "<<<"})

# Grouping tokens stripped before command-name lookup.
_GROUPING_TOKENS = frozenset({"(", ")", "()", "{", "}"})

# The characters shlex treats as punctuation when ``punctuation_chars=True``.
# Runs of them are emitted as a single token (``>|``, ``&>>``, ``|&``, …), so
# operators must be classified by inspecting the whole token — enumerating
# individual redirect spellings misses the combined forms.
_PUNCTUATION_CHARS = frozenset("();<>|&")

# Operator tokens that are understood and permitted. Anything else made purely
# of punctuation is rejected (default-deny) rather than silently folded into
# the current command's argument list.
_KNOWN_OPERATORS = _COMMAND_SEPARATORS | _INPUT_REDIRECTS | _GROUPING_TOKENS


def _is_operator(token: str) -> bool:
    """Whether *token* consists entirely of shell punctuation characters."""
    return bool(token) and all(char in _PUNCTUATION_CHARS for char in token)


def _tokenise(line: str) -> list[str]:
    """Tokenise a single line of shell input.

    Uses :class:`shlex.shlex` in POSIX mode with ``punctuation_chars``
    so that operators (``|``, ``&&``, ``>``, …) are emitted as their
    own tokens.

    Raises:
        ValueError: On malformed input (unmatched quotes, etc.).
    """
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = False
    return list(lexer)


def _split_commands(tokens: list[str]) -> list[list[str]]:
    """Split a flat token list on command-separator operators."""
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _COMMAND_SEPARATORS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _validate_command(cmd: str, args: list[str], root: Path) -> str | None:
    """Validate a single command against the tiered allowlist.

    Returns ``None`` when the command is allowed, or a denial reason string.
    """
    # cd: allow relative paths only, check ALL args
    if cmd == "cd":
        reason = _validate_cd(args)
    # Tier 1: Inherently read-only — allow with any flags
    elif cmd in TIER1_INHERENTLY_READONLY:
        reason = None
    # Tier 2: Conditionally read-only — block write-enabling flags
    elif cmd in TIER2_WRITE_FLAGS:
        reason = _validate_tier2(cmd, args)
    # Tier 3: Git — subcommand-level validation
    elif cmd == "git":
        reason = _validate_git(args)
    else:
        return f"Command not allowed: {cmd}"

    if reason is not None:
        return reason

    # Path confinement applies to every allowlisted command: being read-only
    # says nothing about *what* may be read. Checked last so that a rejected
    # command is reported as such rather than as a path problem.
    return _validate_paths(root, args)


# --- cd validation --------------------------------------------------------


def _validate_cd(args: list[str]) -> str | None:
    """Validate cd arguments — block absolute paths, tilde, env vars."""
    for arg in args:
        if arg.startswith("/"):
            return f"cd to absolute path not allowed: {arg}"
        if arg.startswith("~"):
            return "cd with tilde expansion not allowed"
        if arg.startswith("$"):
            return "cd with variable expansion not allowed"
        if arg == "-":
            return "cd to previous directory not allowed"
        if arg == "--":
            continue  # separator, check next arg
    return None


# --- Tier 2 validation ----------------------------------------------------


def _validate_tier2(cmd: str, args: list[str]) -> str | None:
    """Block write-enabling flags on conditionally read-only commands."""
    dangerous = TIER2_WRITE_FLAGS[cmd]
    for arg in args:
        if arg in dangerous:
            return f"{cmd} with '{arg}' not allowed (writes to file)"
        # Also check --flag=value form (e.g. --output=file.txt)
        flag_name = arg.split("=", 1)[0] if "=" in arg else None
        if flag_name and flag_name in dangerous:
            return f"{cmd} with '{flag_name}' not allowed (writes to file)"
    return None


# --- Tier 3: Git validation -----------------------------------------------


def _validate_git(args: list[str]) -> str | None:
    """Validate a git command's subcommand and flags."""
    subcmd = get_git_subcommand(args)
    if subcmd is None:
        return "git top-level option injecting config or executables not allowed"

    # Subcommands that render diffs share the diff option surface
    if subcmd in GIT_DIFF_RENDERING_SUBCOMMANDS:
        return _validate_git_diff_options(subcmd, args)

    # Truly read-only subcommands — any flags are safe
    if subcmd in GIT_READONLY_SUBCOMMANDS:
        if subcmd == "grep":
            return _validate_git_grep(args)
        return None

    # Dual-mode subcommands (branch, tag) — check flags + positional args
    if subcmd in GIT_DUAL_MODE_SUBCOMMANDS:
        return _validate_git_dual_mode(subcmd, args)

    # Remote — sub-subcommand level validation
    if subcmd == "remote":
        return _validate_git_remote(args)

    return f"git {subcmd} not allowed"


def _validate_git_grep(args: list[str]) -> str | None:
    """Block the pager-invoking flags on ``git grep``."""
    for arg in args:
        flag = arg.split("=", 1)[0] if arg.startswith("--") and "=" in arg else arg
        if flag in GIT_GREP_PAGER_FLAGS:
            return f"git grep with '{flag}' not allowed (runs a pager program)"
        # -O takes its pager inline too, e.g. ``-O/tmp/evil``.
        if arg.startswith("-O") and arg != "-O":
            return "git grep with '-O' not allowed (runs a pager program)"
    return None


def _validate_git_diff_options(subcmd: str, args: list[str]) -> str | None:
    """Block file-writing and program-running diff options on log/show/diff."""
    for arg in args:
        flag = arg.split("=", 1)[0] if arg.startswith("--") else arg
        if flag in GIT_DIFF_WRITE_FLAGS:
            return f"git {subcmd} with '{flag}' not allowed (writes to file)"
        if flag in GIT_DIFF_EXEC_FLAGS:
            return f"git {subcmd} with '{flag}' not allowed (runs a diff driver)"
    return None


def _validate_git_dual_mode(subcmd: str, args: list[str]) -> str | None:
    """Reject mutating flags or positional args on ``git branch`` / ``git tag``."""
    if subcmd == "branch":
        mutating = GIT_BRANCH_MUTATING_FLAGS
        flags_with_value = GIT_BRANCH_FLAGS_WITH_VALUE
    else:
        mutating = GIT_TAG_MUTATING_FLAGS
        flags_with_value = GIT_TAG_FLAGS_WITH_VALUE

    # Check for mutating flags
    past_subcmd = False
    for arg in args:
        if not past_subcmd:
            if arg == subcmd:
                past_subcmd = True
            continue
        if arg in mutating:
            return f"git {subcmd} with '{arg}' not allowed (mutating)"
        # Check --flag=value form (e.g. --set-upstream-to=origin/main)
        if "=" in arg:
            flag_name = arg.split("=", 1)[0]
            if flag_name in mutating:
                return f"git {subcmd} with '{flag_name}' not allowed (mutating)"

    # Check for positional args (= creating a branch/tag)
    if _has_positional_args(args, subcmd, flags_with_value):
        return f"git {subcmd} with positional args not allowed (creates {subcmd})"

    return None


def _validate_git_remote(args: list[str]) -> str | None:
    """Validate ``git remote`` — allow only read-only sub-subcommands."""
    # Find the sub-subcommand (first positional arg after "remote")
    past_remote = False
    for arg in args:
        if not past_remote:
            if arg == "remote":
                past_remote = True
            continue
        if arg.startswith("-"):
            continue
        # First positional arg after "remote" is the sub-subcommand
        if arg in GIT_REMOTE_SAFE_SUBCOMMANDS:
            return None
        if arg in GIT_REMOTE_MUTATING_SUBCOMMANDS:
            return f"git remote {arg} not allowed (mutating)"
        return f"git remote {arg} not allowed"

    # No sub-subcommand — bare "git remote" or "git remote -v" — safe
    return None


# ---------------------------------------------------------------------------
# Public validation
# ---------------------------------------------------------------------------


def _validate_line(line: str, root: Path) -> str | None:
    """Validate a single line of shell input.

    Returns ``None`` when the line is safe, or a denial reason string.
    """
    try:
        tokens = _tokenise(line)
    except ValueError as exc:
        return f"Unparseable command: {exc}"

    # Classify operator tokens: any redirect that can write a file is rejected,
    # and unrecognised operators are rejected outright so a construct we do not
    # model cannot smuggle a second command past _split_commands().
    for token in tokens:
        if not _is_operator(token):
            continue
        if ">" in token:
            return f"Output redirect '{token}' not allowed"
        if token not in _KNOWN_OPERATORS:
            return f"Unsupported shell operator '{token}' not allowed"

    # Split on operators and validate each simple command
    for cmd_tokens in _split_commands(tokens):
        # Strip subshell / brace-group syntax
        words = [t for t in cmd_tokens if t not in _GROUPING_TOKENS]
        if not words:
            continue
        reason = _validate_command(words[0], words[1:], root)
        if reason is not None:
            return reason

    return None


def check_bash_command(
    cmd: str,
    root: Path,
) -> PermissionResultAllow | PermissionResultDeny:
    """Validate a Bash command for read-only safety, confined to *root*.

    Tokenises the command with :mod:`shlex`, rejects dangerous shell
    constructs (substitution, output redirects), then validates each
    simple command against a tiered allowlist and confines every path
    argument to *root*.
    Uses **default-deny**: parse failures and unknown commands are rejected.
    """
    if not cmd:
        logger.debug("bash command DENIED (empty)")
        return PermissionResultDeny(message="Empty command")

    # Pre-scan: reject command / process substitution on the raw string.
    # This is intentionally broad (matches inside quotes too) because our
    # allowlist is small and legitimate use of these in allowlisted commands
    # is effectively zero.
    if "$(" in cmd or "`" in cmd:
        logger.debug("bash command DENIED (substitution): %s", cmd)
        return PermissionResultDeny(message="Command substitution not allowed")
    if "<(" in cmd or ">(" in cmd:
        logger.debug("bash command DENIED (substitution): %s", cmd)
        return PermissionResultDeny(message="Process substitution not allowed")

    # Parameter expansion is scanned on the raw string, not per token: shlex
    # emits ``$`` as its own token, so ``$HOME/.ssh/id_rsa`` would otherwise
    # reach the path check as the harmless-looking relative ``HOME/.ssh/id_rsa``
    # and the shell would expand it to an absolute path afterwards. Narrow by
    # design — a trailing ``$`` (the regex anchor in ``grep 'foo$'``) is fine.
    if _VARIABLE_EXPANSION.search(cmd):
        logger.debug("bash command DENIED (variable expansion): %s", cmd)
        return PermissionResultDeny(message="Variable expansion not allowed")

    # Validate each line independently (handles newline injection).
    for line in cmd.split("\n"):
        line = line.strip()
        if not line:
            continue
        reason = _validate_line(line, root)
        if reason is not None:
            logger.debug("bash command DENIED (%s): %s", reason, cmd)
            return PermissionResultDeny(message=reason)

    logger.debug("bash command ALLOWED: %s", cmd)
    return PermissionResultAllow()


# ---------------------------------------------------------------------------
# SDK callbacks
# ---------------------------------------------------------------------------


# Input fields naming a filesystem location on the read-only file tools.
_FILE_TOOL_PATH_FIELDS = ("file_path", "path", "notebook_path")


def create_read_only_tool_handler(root: Path) -> CanUseTool:
    """Build the permission callback for a subagent confined to *root*.

    The callback is a closure rather than a module-level function because
    the repository path is only known per run, and confinement must not be
    something a caller can forget to pass.
    """

    async def read_only_tool_handler(
        tool_name: str,
        input_data: dict[str, Any],
        _context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Permission callback enforcing read-only access for Claude SDK tools.

        Called by the Claude SDK control protocol for tool invocations that
        require permission.  Allows read-only operations inside *root* and
        blocks mutations.
        """
        # Allow search and read tools, provided they stay inside the repo
        if tool_name in ("Read", "Grep", "Glob"):
            for field in (*_FILE_TOOL_PATH_FIELDS, "pattern"):
                value = input_data.get(field)
                if not isinstance(value, str) or not value:
                    continue
                # A Grep/Glob ``pattern`` is normally a regex or glob rooted at
                # the working directory; only check it when it actually
                # addresses a location (``/etc/**``), never a bare regex.
                if field == "pattern" and not _is_path_like(value):
                    continue
                if not _is_within(root, value):
                    logger.debug(
                        "%s DENIED (%s outside repository): %s", tool_name, field, value
                    )
                    return PermissionResultDeny(
                        message=(f"Path outside the repository not allowed: {value}")
                    )
            return PermissionResultAllow(updated_input=input_data)

        # Allow MCP project tools (explicitly configured by the user)
        if tool_name.startswith("mcp__"):
            return PermissionResultAllow(updated_input=input_data)

        # Bash: fine-grained command filtering via AST
        if tool_name == "Bash":
            result = check_bash_command((input_data.get("command") or "").strip(), root)
            if isinstance(result, PermissionResultAllow):
                return PermissionResultAllow(updated_input=input_data)
            return result

        # Block everything else (Write, Edit, etc.)
        return PermissionResultDeny(
            message=f"Tool '{tool_name}' not allowed in read-only mode"
        )

    return read_only_tool_handler


async def pretool_noop_hook(
    _input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> SyncHookJSONOutput:
    """Required workaround: keeps the stream open for ``can_use_tool`` callback.

    See: https://github.com/anthropics/claude-code/issues/18735
    """
    return SyncHookJSONOutput(continue_=True)

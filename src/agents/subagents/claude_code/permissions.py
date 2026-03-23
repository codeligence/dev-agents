"""Read-only permission handler for the Claude Agent SDK.

Uses ``shlex`` (stdlib) to tokenise Bash commands, then applies a
default-deny allowlist.  Blocks command/process substitution, output
redirects, and any command not explicitly allowlisted.

Commands are classified into three tiers:

- **Tier 1 — Inherently read-only**: Commands that cannot write to the
  filesystem regardless of flags (e.g. ``ls``, ``cat``, ``grep``).
  Allowed with any arguments.
- **Tier 2 — Conditionally read-only**: Commands that are read-only by
  default but have specific write-enabling flags (e.g. ``sort -o``,
  ``find -exec``).  Blocked only when those flags appear.
- **Tier 3 — Complex (git)**: Requires subcommand-level validation.
  ``git -c`` is blocked unconditionally; each subcommand is classified
  as fully read-only, read-only with restrictions, or dual-mode
  (list vs. create).

Permission evaluation order (from SDK docs):
    Hooks -> Deny rules -> Permission mode -> Allow rules -> canUseTool callback
"""

from typing import Any
import shlex

from claude_agent_sdk.types import (
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
        {"-exec", "-execdir", "-delete", "-ok", "-okdir", "-fprint", "-fls", "-fprintf"}
    ),
}

# Tier 3 — Git constants

# Git subcommands that are truly read-only — any flags are safe.
GIT_READONLY_SUBCOMMANDS = frozenset(
    {"log", "show", "status", "ls-files", "rev-parse", "grep"}
)

# Git subcommands that are read-only but have a write-enabling --output flag.
GIT_READONLY_WITH_OUTPUT_FLAG = frozenset({"diff"})

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_git_subcommand(args: list[str]) -> str | None:
    """Extract the git subcommand, skipping flags like ``-C <path>``.

    Stops at ``-c`` (config override) and returns ``None`` so the caller
    can reject the entire command.

    Args:
        args: The argument list *after* the ``git`` token itself.

    Returns:
        The first positional argument (i.e. the subcommand), or ``None``.
    """
    i = 0
    while i < len(args):
        word = args[i]
        # -c is a config override that can execute arbitrary commands — reject
        if word == "-c":
            return None
        if word in GIT_FLAGS_WITH_VALUE:
            i += 2  # Skip flag and its value
            continue
        if word.startswith("-"):
            i += 1
            continue
        return word
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

# Operators that separate independent commands in a token stream.
_COMMAND_SEPARATORS = frozenset({"|", "||", "&&", ";", "&"})

# Output redirect operators — these can overwrite files.
_OUTPUT_REDIRECTS = frozenset({">", ">>", ">&", "&>"})

# Grouping tokens stripped before command-name lookup.
_GROUPING_TOKENS = frozenset({"(", ")", "()", "{", "}"})


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


def _validate_command(cmd: str, args: list[str]) -> str | None:
    """Validate a single command against the tiered allowlist.

    Returns ``None`` when the command is allowed, or a denial reason string.
    """
    # cd: allow relative paths only, check ALL args
    if cmd == "cd":
        return _validate_cd(args)

    # Tier 1: Inherently read-only — allow with any flags
    if cmd in TIER1_INHERENTLY_READONLY:
        return None

    # Tier 2: Conditionally read-only — block write-enabling flags
    if cmd in TIER2_WRITE_FLAGS:
        return _validate_tier2(cmd, args)

    # Tier 3: Git — subcommand-level validation
    if cmd == "git":
        return _validate_git(args)

    return f"Command not allowed: {cmd}"


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
        return "git -c (config override) not allowed"

    # Truly read-only subcommands — any flags are safe
    if subcmd in GIT_READONLY_SUBCOMMANDS:
        return None

    # Read-only subcommands with --output flag restriction
    if subcmd in GIT_READONLY_WITH_OUTPUT_FLAG:
        return _validate_git_no_output(subcmd, args)

    # Dual-mode subcommands (branch, tag) — check flags + positional args
    if subcmd in GIT_DUAL_MODE_SUBCOMMANDS:
        return _validate_git_dual_mode(subcmd, args)

    # Remote — sub-subcommand level validation
    if subcmd == "remote":
        return _validate_git_remote(args)

    return f"git {subcmd} not allowed"


def _validate_git_no_output(subcmd: str, args: list[str]) -> str | None:
    """Block --output flag on git diff and similar."""
    for arg in args:
        if arg == "--output" or arg.startswith("--output="):
            return f"git {subcmd} with '--output' not allowed"
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


def _validate_line(line: str) -> str | None:
    """Validate a single line of shell input.

    Returns ``None`` when the line is safe, or a denial reason string.
    """
    try:
        tokens = _tokenise(line)
    except ValueError as exc:
        return f"Unparseable command: {exc}"

    # Check for output redirects in token stream
    for token in tokens:
        if token in _OUTPUT_REDIRECTS:
            return f"Output redirect '{token}' not allowed"

    # Split on operators and validate each simple command
    for cmd_tokens in _split_commands(tokens):
        # Strip subshell / brace-group syntax
        words = [t for t in cmd_tokens if t not in _GROUPING_TOKENS]
        if not words:
            continue
        reason = _validate_command(words[0], words[1:])
        if reason is not None:
            return reason

    return None


def check_bash_command(
    cmd: str,
) -> PermissionResultAllow | PermissionResultDeny:
    """Validate a Bash command for read-only safety.

    Tokenises the command with :mod:`shlex`, rejects dangerous shell
    constructs (substitution, output redirects), then validates each
    simple command against a tiered allowlist.
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

    # Validate each line independently (handles newline injection).
    for line in cmd.split("\n"):
        line = line.strip()
        if not line:
            continue
        reason = _validate_line(line)
        if reason is not None:
            logger.debug("bash command DENIED (%s): %s", reason, cmd)
            return PermissionResultDeny(message=reason)

    logger.debug("bash command ALLOWED: %s", cmd)
    return PermissionResultAllow()


# ---------------------------------------------------------------------------
# SDK callbacks
# ---------------------------------------------------------------------------


async def read_only_tool_handler(
    tool_name: str,
    input_data: dict[str, Any],
    _context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Permission callback enforcing read-only access for Claude SDK tools.

    Called by the Claude SDK control protocol for tool invocations that
    require permission.  Allows read-only operations and blocks mutations.
    """
    # Allow search and read tools
    if tool_name in ("Read", "Grep", "Glob"):
        return PermissionResultAllow(updated_input=input_data)

    # Allow MCP project tools (explicitly configured by the user)
    if tool_name.startswith("mcp__"):
        return PermissionResultAllow(updated_input=input_data)

    # Bash: fine-grained command filtering via AST
    if tool_name == "Bash":
        result = check_bash_command((input_data.get("command") or "").strip())
        if isinstance(result, PermissionResultAllow):
            return PermissionResultAllow(updated_input=input_data)
        return result

    # Block everything else (Write, Edit, etc.)
    return PermissionResultDeny(
        message=f"Tool '{tool_name}' not allowed in read-only mode"
    )


async def pretool_noop_hook(
    _input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> SyncHookJSONOutput:
    """Required workaround: keeps the stream open for ``can_use_tool`` callback.

    See: https://github.com/anthropics/claude-code/issues/18735
    """
    return SyncHookJSONOutput(continue_=True)

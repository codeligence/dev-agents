import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional, List

from agents.agents.gitchatbot.models import ChatbotContext
from core.config import BaseConfig
from core.config import get_default_config
from core.project_config import ProjectConfigFactory
from core.integrations import get_provider_registry
from core.log import get_logger
from integrations.git.changed_file import ChangedFile, ChangedFileSet
from integrations.git.config import GitRepositoryConfig
from integrations.git.models import GitDiffContext, DiffMetadata

logger = get_logger(logger_name="GitRepository", level="DEBUG")

EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# Global tracking for per-repository pull rate limiting
_last_pull_times: Dict[str, float] = {}
_pull_locks: Dict[str, threading.Lock] = {}


class GitRepository:
    """Repository pattern implementation for git diff operations.

    Combines low-level git operations with business logic for PR and WorkItem workflows.
    Follows Repository Pattern with dependency injection for external services.
    """

    def __init__(
            self,
            base_config: Optional[BaseConfig] = None
    ) -> None:
        self.base_config = base_config or get_default_config()

        # Setup project configuration
        project_factory = ProjectConfigFactory(self.base_config)
        self.project_config = project_factory.get_default_project_config()

        # Use GitRepositoryConfig to get repository path
        git_config = GitRepositoryConfig.from_project_config(self.project_config)
        self.repo_path = Path(git_config.get_repo_dir()).resolve()

        # Setup provider registry
        self.provider_registry = get_provider_registry()

        # Auto-pull with rate limiting if enabled
        self._auto_pull_if_needed(git_config)

    def get_diff_from_branches(
            self,
            source_branch: str,
            target_branch: str,
            context: str = "Direct branch comparison",
            include_patch: bool = True
    ) -> GitDiffContext:
        """Get diff context from direct branch comparison.

        Parameters
        ----------
        source_branch: the feature branch (head of PR)
        target_branch: the base branch (e.g. *develop*, *main*)
        context: description of the change context
        include_patch: include patch text for each file (defaults to True)

        Returns
        -------
        GitDiffContext with git data and minimal business context
        """
        changed_files = self._get_changed_file_set(source_branch, target_branch, include_patch=include_patch)
        file_diffs = changed_files.get_file_diffs()

        # Calculate metadata
        total_files = len(changed_files.files)
        total_insertions = sum(f.insertions or 0 for f in changed_files.files)
        total_deletions = sum(f.deletions or 0 for f in changed_files.files)

        metadata = DiffMetadata(
            total_files_changed=total_files,
            line_counts={
                'insertions': total_insertions,
                'deletions': total_deletions,
                'total': total_insertions + total_deletions
            }
        )

        return GitDiffContext(
            changed_files=changed_files,
            file_diffs=file_diffs,
            source_branch=source_branch,
            target_branch=target_branch,
            repo_path=str(self.repo_path),
            context=context,
            metadata=metadata
        )

    def _get_changed_file_set(
            self,
            source_branch: str,
            target_branch: str,
            *,
            include_patch: bool = False,
    ) -> ChangedFileSet:
        """Return a **ChangedFileSet** that mirrors a PR diff.

        Parameters
        ----------
        source_branch: the feature branch (head of PR)
        target_branch: the base branch (e.g. *develop*, *main*)
        include_patch: include heavy patch text for each file (defaults to *False*)
        """
        src_ref = self._resolve_branch(source_branch)
        tgt_ref = self._resolve_branch(target_branch)

        logger.debug(
            f"Getting diff between target branch '{target_branch}' and source branch '{source_branch}' using three dots diff")

        # Use the three dots syntax for git diff (shows changes between branches excluding common ancestors)
        name_status = self._parse_name_status_three_dots(tgt_ref, src_ref)
        numstat = self._parse_numstat_three_dots(tgt_ref, src_ref)

        logger.debug("Parsed name_status and numstat: %s, %s", name_status, numstat)

        files: List[ChangedFile] = []
        for path, status in name_status.items():
            insertions, deletions, binary_flag = numstat.get(path, (None, None, False))
            patch = (
                self._git_output(f"git diff {tgt_ref}...{src_ref} -- {shlex.quote(path)}")
                if include_patch and not binary_flag
                else None
            )
            files.append(
                ChangedFile(
                    path=path,
                    status=status,
                    insertions=insertions,
                    deletions=deletions,
                    binary=binary_flag,
                    patch=patch,
                )
            )

        return ChangedFileSet(
            source_branch=source_branch,
            target_branch=target_branch,
            files=sorted(files, key=lambda f: f.path),
        )

    async def get_diff_from_pr(self, pullrequest_id: str, issue_id: Optional[int] = None) -> GitDiffContext:
        """Get diff context from PR ID with optional WorkItem context.

        Parameters
        ----------
        pullrequest_id: Pull Request ID
        issue_id: Optional Work Item ID for additional context

        Returns
        -------
        GitDiffContext with git data and business context from PR/WorkItem
        """
        # Get PR details to resolve branches using provider system
        pr_provider = self.provider_registry.resolve_pullrequest_provider(self.project_config)
        if not pr_provider:
            raise ValueError("No pull request provider available for current configuration")

        pr_model = await pr_provider.load(pullrequest_id)

        # Extract branch information from the model using refs lists
        source_branch = self._resolve_refs_to_branch(pr_model.source_refs)
        target_branch = self._resolve_refs_to_branch(pr_model.target_refs)

        if not source_branch or not target_branch:
            raise ValueError(f"Pull request {pullrequest_id} - could not resolve valid source/target references")

        context = f"Pull Request #{pullrequest_id}"

        if issue_id:
            issue_provider = self.provider_registry.resolve_issue_provider(self.project_config)
            if issue_provider:
                issue_model = await issue_provider.load(str(issue_id))
                # Extract title from context - this is a simplified approach
                issue_title = f"Issue #{issue_id}"
                context = f"Pull Request #{pullrequest_id} - {issue_title}\n\n" + issue_model.context

        # Get the actual diff data
        changed_files = self._get_changed_file_set(source_branch, target_branch, include_patch=True)
        file_diffs = changed_files.get_file_diffs()

        # Calculate metadata
        total_files = len(changed_files.files)
        total_insertions = sum(f.insertions or 0 for f in changed_files.files)
        total_deletions = sum(f.deletions or 0 for f in changed_files.files)

        metadata = DiffMetadata(
            total_files_changed=total_files,
            line_counts={
                'insertions': total_insertions,
                'deletions': total_deletions,
                'total': total_insertions + total_deletions
            }
        )

        return GitDiffContext(
            changed_files=changed_files,
            file_diffs=file_diffs,
            source_branch=source_branch,
            target_branch=target_branch,
            repo_path=str(self.repo_path),
            context=context,
            metadata=metadata,
        )

    def _auto_pull_if_needed(self, git_config: GitRepositoryConfig) -> None:
        """Execute auto-pull with per-repository rate limiting if conditions are met.
        
        Args:
            git_config: GitRepositoryConfig instance for accessing settings
        """
        # Check if auto-pull is enabled
        if not git_config.get_auto_pull():
            logger.debug("Auto-pull is disabled, skipping")
            return

        repo_path_str = str(self.repo_path)
        pull_interval = git_config.get_pull_interval_seconds()
        current_time = time.time()

        # Get or create lock for this repository path
        if repo_path_str not in _pull_locks:
            _pull_locks[repo_path_str] = threading.Lock()

        # Use lock to prevent concurrent pulls for the same repository
        with _pull_locks[repo_path_str]:
            last_pull_time = _last_pull_times.get(repo_path_str, 0)
            
            # Check if enough time has passed since last pull
            if current_time - last_pull_time >= pull_interval:
                try:
                    logger.debug(f"Auto-pulling repository at {repo_path_str}")
                    result = self.pull()
                    logger.debug(f"Auto-pull completed: {result}")
                    # Update last pull time on success
                    _last_pull_times[repo_path_str] = current_time
                except Exception as e:
                    logger.warning(f"Auto-pull failed for {repo_path_str}: {e}")
            else:
                time_remaining = pull_interval - (current_time - last_pull_time)
                logger.debug(f"Auto-pull rate limited for {repo_path_str}, {time_remaining:.1f}s remaining")

    # --------------------- low‑level helpers ------------------------------

    def _git_output(self, cmd: str) -> str:
        """Run *cmd* in the repo and return **stdout** as *str* (strip tail newline)."""
        logger.debug("Running git command: %s", cmd)
        return subprocess.check_output(
            cmd, shell=True, cwd=self.repo_path
        ).decode('utf-8').strip()

    def pull(self) -> str:
        """Execute git pull in the repository to update it with remote changes."""
        logger.debug("Pulling latest changes from remote")
        return self._git_output("git pull")

    # ------------------------------------------------------------------

    def _resolve_branch_safe(self, branch: str) -> Optional[str]:
        """Return the first valid reference for *branch*, or None if not found."""
        for candidate in (branch, f"origin/{branch}", f"remotes/origin/{branch}"):
            try:
                self._git_output(f"git rev-parse --verify {shlex.quote(candidate)}")
                return candidate
            except subprocess.CalledProcessError:
                continue
        return None

    def _resolve_branch(self, branch: str) -> str:
        """Return the first valid reference for *branch* (tries local, origin/, remotes/origin/)."""
        result = self._resolve_branch_safe(branch)
        if result is None:
            raise ValueError(f"Branch ref '{branch}' not found (local or remote)")
        return result

    def _resolve_refs_to_branch(self, refs: List[str]) -> Optional[str]:
        """Resolve first valid reference from a list of refs (branches/commits)."""
        for ref in refs:
            resolved = self._resolve_branch_safe(ref)
            if resolved:
                return resolved
        return None

    # ------------------------------------------------------------------

    def _merge_base(self, src: str, tgt: str) -> str:
        try:
            return self._git_output(f"git merge-base {shlex.quote(src)} {shlex.quote(tgt)}")
        except subprocess.CalledProcessError:
            return EMPTY_TREE_HASH

    # ------------------------------------------------------------------

    def _parse_name_status_three_dots(self, tgt: str, src: str) -> Dict[str, str]:
        """Return mapping *path -> status letter* using a three dots git diff."""
        output = self._git_output(f"git diff --name-status -M -C {tgt}...{src}")
        logger.debug("Got name_status output: %s", output)
        mapping: Dict[str, str] = {}
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0]
            if status.startswith("R") or status.startswith("C"):
                # Rename/copy: status is like 'R100' – take the new path (last column)
                path = parts[-1]
                mapping[path] = status[0]
            else:
                path = parts[1]
                mapping[path] = status
        return mapping

    def _parse_numstat_three_dots(self, tgt: str, src: str) -> Dict[str, tuple[int | None, int | None, bool]]:
        """Return mapping *path -> (insertions, deletions, binary)* using three dots git diff."""
        output = self._git_output(f"git diff --numstat -M -C {tgt}...{src}")
        result: Dict[str, tuple[int | None, int | None, bool]] = {}
        for line in output.splitlines():
            if not line.strip():
                continue
            ins, dels, path = line.split("\t", 2)
            binary_flag = ins == "-" or dels == "-"
            insertions = None if binary_flag else int(ins)
            deletions = None if binary_flag else int(dels)
            result[path] = (insertions, deletions, binary_flag)
        return result

"""Git operations via GitPython."""

import os
from pathlib import Path
from typing import List, Optional

import git as gitpython


class GitManager:
    """Manages git operations for the working directory."""

    def __init__(self, working_dir: str = ".") -> None:
        self.working_dir = os.path.abspath(working_dir)
        self._repo: Optional[gitpython.Repo] = None

    def _get_repo(self) -> gitpython.Repo:
        if self._repo is None:
            try:
                self._repo = gitpython.Repo(self.working_dir, search_parent_directories=True)
            except gitpython.InvalidGitRepositoryError:
                raise RuntimeError(
                    f"Not a git repository: {self.working_dir}. Run 'git init' first."
                )
        return self._repo

    def is_repo(self) -> bool:
        try:
            self._get_repo()
            return True
        except RuntimeError:
            return False

    def file_tree(self, max_depth: int = 3) -> str:
        """Return a simple text representation of the file tree."""
        lines: List[str] = []
        root = Path(self.working_dir)

        def _walk(path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            entries = [
                e for e in entries
                if e.name not in (".git", "__pycache__", "node_modules", ".venv", "venv")
            ]
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        lines.append(root.name + "/")
        _walk(root, "", 1)
        return "\n".join(lines)

    def diff(self, staged: bool = False) -> str:
        """Get the current diff (working tree vs HEAD, or staged)."""
        repo = self._get_repo()
        try:
            if staged:
                return repo.git.diff("--cached")
            return repo.git.diff("HEAD")
        except gitpython.GitCommandError:
            # No commits yet — show all tracked file contents
            return repo.git.diff()

    def diff_stat(self) -> str:
        """Short diff stat summary."""
        repo = self._get_repo()
        try:
            return repo.git.diff("HEAD", "--stat")
        except gitpython.GitCommandError:
            return ""

    def has_changes(self) -> bool:
        repo = self._get_repo()
        return repo.is_dirty(untracked_files=True)

    def create_branch(self, name: str) -> str:
        """Create and checkout a new branch. Returns the branch name."""
        repo = self._get_repo()
        repo.git.checkout("-b", name)
        return name

    def current_branch(self) -> str:
        repo = self._get_repo()
        return repo.active_branch.name

    def stage_all(self) -> None:
        repo = self._get_repo()
        repo.git.add("-A")

    def commit(self, message: str) -> str:
        """Stage all and commit. Returns the commit hash."""
        repo = self._get_repo()
        repo.git.add("-A")
        repo.git.commit("-m", message)
        return repo.head.commit.hexsha[:8]

    def untracked_files(self) -> List[str]:
        repo = self._get_repo()
        return repo.untracked_files

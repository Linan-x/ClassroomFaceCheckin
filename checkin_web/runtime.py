"""Runtime paths and import setup shared by Flask entry points."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    core_root: Path
    data_root: Path
    workspace_root: Path

    @classmethod
    def discover(cls) -> "RuntimePaths":
        project_root = Path(__file__).resolve().parents[1]
        return cls(
            project_root=project_root,
            core_root=project_root / "core",
            data_root=project_root / "data",
            workspace_root=project_root / "work_space",
        )

    def configure_imports(self) -> None:
        """Make local application packages importable without changing CWD."""
        for path in (self.project_root, self.core_root):
            path_string = str(path)
            if path_string not in sys.path:
                sys.path.insert(0, path_string)


PATHS = RuntimePaths.discover()


def configure_runtime() -> RuntimePaths:
    """Initialize deterministic import paths while preserving the caller's CWD."""
    PATHS.configure_imports()
    return PATHS

from __future__ import annotations

from pathlib import Path

DENIED_NAMES = {".env", ".git", "id_rsa", "id_ed25519"}
DENIED_SUFFIXES = {".pem", ".key", ".p12"}


class PolicyError(PermissionError):
    pass


class ProjectPolicy:
    """Resolve paths inside one project root and refuse sensitive files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise PolicyError(f"project root does not exist: {self.root}")

    def resolve(self, raw_path: str, *, must_exist: bool = False) -> Path:
        candidate = (self.root / raw_path).expanduser().resolve()
        if candidate != self.root and not candidate.is_relative_to(self.root):
            raise PolicyError(f"path escapes project root: {raw_path}")
        if self.is_denied(candidate):
            raise PolicyError(f"access denied by policy: {raw_path}")
        if must_exist and not candidate.exists():
            raise PolicyError(f"path does not exist: {raw_path}")
        return candidate

    def is_denied(self, path: Path) -> bool:
        parts = path.relative_to(self.root).parts if path != self.root else ()
        if any(part in DENIED_NAMES for part in parts):
            return True
        return path.suffix.lower() in DENIED_SUFFIXES

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))

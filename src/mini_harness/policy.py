
from pathlib import Path
from typing import ClassVar

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


class CommandPolicy:
    """Allow only the fixed test and lint commands, never a user supplied shell line."""

    ALLOWED_EXECUTABLES: ClassVar[set[str]] = {"python", "python3", "pytest", "ruff"}
    FORBIDDEN_TOKENS: ClassVar[set[str]] = {
        "rm",
        "sudo",
        "curl",
        "wget",
        "git",
        "bash",
        "sh",
        "zsh",
        "powershell",
        "cmd",
    }
    SHELL_CHARS: ClassVar[set[str]] = set(";|&><`$()")

    def check(self, argv: list[str]) -> None:
        if not argv:
            raise PolicyError("empty command")
        executable = Path(argv[0]).name.lower()
        if executable not in self.ALLOWED_EXECUTABLES and not executable.startswith("python"):
            raise PolicyError(f"executable is not allowed: {argv[0]}")
        for token in argv[1:]:
            if token in self.FORBIDDEN_TOKENS:
                raise PolicyError(f"forbidden command token: {token}")
            if any(char in token for char in self.SHELL_CHARS):
                raise PolicyError(f"shell metacharacters are not allowed: {token}")

    def test_command(self) -> list[str]:
        import sys

        return [sys.executable, "-m", "pytest", "-q"]

    def lint_command(self) -> list[str]:
        import sys

        return [sys.executable, "-m", "ruff", "check", "."]

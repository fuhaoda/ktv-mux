from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import KtvError, MissingDependencyError


@dataclass
class CommandResult:
    args: list[str]
    stdout: str
    stderr: str


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MissingDependencyError(f"required command not found: {name}")
    return path


def run_command(args: Sequence[str | Path], *, cwd: Path | None = None) -> CommandResult:
    str_args = [str(arg) for arg in args]
    try:
        completed = subprocess.run(
            str_args,
            cwd=str(cwd) if cwd else None,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"required command not found: {str_args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise KtvError(f"command failed: {' '.join(str_args)}\n{message}") from exc
    return CommandResult(str_args, completed.stdout, completed.stderr)


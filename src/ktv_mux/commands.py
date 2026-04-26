from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

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
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"required command not found: {str_args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise KtvError(f"command failed: {' '.join(str_args)}\n{message}") from exc
    return CommandResult(str_args, completed.stdout, completed.stderr)


def run_command_logged(
    args: Sequence[str | Path],
    *,
    log_path: Path,
    cwd: Path | None = None,
) -> CommandResult:
    str_args = [str(arg) for arg in args]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_parts: list[str] = []
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(str_args) + "\n\n")
            process = subprocess.Popen(
                str_args,
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                output_parts.append(line)
                log.write(line)
                log.flush()
            return_code = process.wait()
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"required command not found: {str_args[0]}") from exc

    stdout = "".join(output_parts)
    if return_code != 0:
        tail = "".join(output_parts[-80:]).strip()
        raise KtvError(f"command failed: {' '.join(str_args)}\n{tail}")
    return CommandResult(str_args, stdout, "")

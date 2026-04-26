from __future__ import annotations

import os
import select
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


def run_command(
    args: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    cancel_file: Path | None = None,
) -> CommandResult:
    str_args = [str(arg) for arg in args]
    if cancel_file is not None:
        return _run_command_monitored(str_args, cwd=cwd, cancel_file=cancel_file)
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
    cancel_file: Path | None = None,
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
            )
            assert process.stdout is not None
            while True:
                if cancel_file is not None and cancel_file.exists() and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise KtvError(f"command canceled: {' '.join(str_args)}")
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                text = ""
                if ready:
                    chunk = os.read(process.stdout.fileno(), 4096)
                    text = chunk.decode("utf-8", errors="replace") if chunk else ""
                if text:
                    output_parts.append(text)
                    log.write(text)
                    log.flush()
                if not text and process.poll() is not None:
                    remainder = process.stdout.read()
                    if remainder:
                        tail_text = remainder.decode("utf-8", errors="replace")
                        output_parts.append(tail_text)
                        log.write(tail_text)
                        log.flush()
                    break
            return_code = process.wait()
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"required command not found: {str_args[0]}") from exc

    stdout = "".join(output_parts)
    if return_code != 0:
        tail = "".join(output_parts[-80:]).strip()
        raise KtvError(f"command failed: {' '.join(str_args)}\n{tail}")
    return CommandResult(str_args, stdout, "")


def _run_command_monitored(
    str_args: list[str],
    *,
    cwd: Path | None,
    cancel_file: Path,
) -> CommandResult:
    output_parts: list[str] = []
    try:
        process = subprocess.Popen(
            str_args,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"required command not found: {str_args[0]}") from exc
    assert process.stdout is not None
    while True:
        if cancel_file.exists():
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise KtvError(f"command canceled: {' '.join(str_args)}")
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if ready:
            chunk = os.read(process.stdout.fileno(), 4096)
            if chunk:
                output_parts.append(chunk.decode("utf-8", errors="replace"))
        if process.poll() is not None:
            remainder = process.stdout.read()
            if remainder:
                output_parts.append(remainder.decode("utf-8", errors="replace"))
            break
    if process.returncode != 0:
        message = "".join(output_parts).strip()
        raise KtvError(f"command failed: {' '.join(str_args)}\n{message}")
    return CommandResult(str_args, "".join(output_parts), "")

"""Isolated process sandboxed code executor with stream capture and process timeout bounds."""

from __future__ import annotations

import builtins
import contextlib
import io
import multiprocessing
import multiprocessing.connection
import sys
import time
import traceback
from typing import Any

from pydantic import BaseModel, Field

# Disallowed builtins and modules that must never be accessible
DISALLOWED_BUILTINS: tuple[str, ...] = (
    "open",
    "importlib",
    "os",
    "sys",
    "subprocess",
    "__import__",
    "eval",
    "exec",
    "breakpoint",
    "input",
)

# Safe builtin functions and types permitted inside sandboxed exec
SAFE_BUILTINS: dict[str, Any] = {
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "print": print,
    "range": range,
    "str": str,
}


class ExecutionResult(BaseModel):
    """Result of an isolated sandboxed code execution."""

    stdout: str = Field(default="", description="Captured standard output stream")
    stderr: str = Field(
        default="", description="Captured standard error stream / diagnostics"
    )
    exit_code: int = Field(
        default=0,
        description="Process exit code (0: success, 1: error, 124: timeout)",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Execution duration in milliseconds",
    )


class ExecuteRequest(BaseModel):
    """Request payload for sandboxed Python code execution."""

    python_code: str = Field(
        ...,
        description="Synthesized or user Python code to execute",
    )
    timeout: float | None = Field(
        default=None,
        description="Optional timeout in seconds (subject to hard ceiling of 2.0s)",
    )


def _sandboxed_worker(
    code: str,
    conn: multiprocessing.connection.Connection,
    safe_builtins: dict[str, Any],
) -> None:
    """Target function executed inside the isolated child process context."""
    # 1. Defensively neutralize disk and network modules in child sys.modules
    for mod in ("os", "subprocess", "importlib", "socket", "urllib", "http", "shutil"):
        sys.modules[mod] = None  # type: ignore[assignment]

    # 2. Defensively strip disk/network builtins from builtins module in child process
    for disallowed in ("open", "__import__", "eval", "input", "breakpoint"):
        if hasattr(builtins, disallowed):
            with contextlib.suppress(AttributeError, TypeError):
                delattr(builtins, disallowed)

    # 3. Capture sys.stdout and sys.stderr using io.StringIO
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture

    exit_code = 0

    # 4. Build restricted execution environment
    restricted_builtins = dict(safe_builtins)
    exec_globals: dict[str, Any] = {
        "__builtins__": restricted_builtins,
        "__name__": "__main__",
        "__doc__": None,
    }

    _native_exec = builtins.exec

    try:
        compiled = compile(code, "<sandboxed_exec>", "exec")
        _native_exec(compiled, exec_globals)
    except SystemExit as exc:
        exit_code = (
            exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        )
    except BaseException:  # noqa: BLE001
        exit_code = 1
        traceback.print_exc(file=stderr_capture)
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        try:
            with contextlib.suppress(Exception):
                conn.send(
                    {
                        "stdout": stdout_capture.getvalue(),
                        "stderr": stderr_capture.getvalue(),
                        "exit_code": exit_code,
                    }
                )
        finally:
            conn.close()


class SandboxedExecutor:
    """Isolated process executor with restricted builtins, stream capture, and hard timeout bounds."""

    HARD_TIMEOUT_CEILING: float = 2.0
    SAFE_BUILTINS: dict[str, Any] = SAFE_BUILTINS

    def __init__(self, timeout: float = 2.0) -> None:
        self.default_timeout = min(max(0.001, timeout), self.HARD_TIMEOUT_CEILING)

    def execute(
        self,
        code: str | ExecuteRequest = "",
        timeout: float | None = None,
        python_code: str | None = None,
    ) -> ExecutionResult:
        """Execute Python code in an isolated multiprocessing process.

        Args:
            code: Source code string or ExecuteRequest model.
            timeout: Optional execution timeout (capped at HARD_TIMEOUT_CEILING of 2.0s).
            python_code: Optional keyword alias for code.

        Returns:
            ExecutionResult with captured stdout, stderr, exit_code, and duration_ms.
        """
        # Resolve code and timeout from parameters or ExecuteRequest
        if isinstance(code, ExecuteRequest):
            effective_code = code.python_code
            if timeout is None and code.timeout is not None:
                timeout = code.timeout
        elif python_code is not None and not code:
            effective_code = python_code
        else:
            effective_code = code

        if timeout is None:
            effective_timeout = self.default_timeout
        else:
            effective_timeout = min(max(0.001, timeout), self.HARD_TIMEOUT_CEILING)

        start_time = time.perf_counter()
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)

        proc = multiprocessing.Process(
            target=_sandboxed_worker,
            args=(effective_code, child_conn, self.SAFE_BUILTINS),
        )

        try:
            proc.start()
            # Close child descriptor in parent process
            child_conn.close()

            proc.join(timeout=effective_timeout)

            if proc.is_alive():
                # Process exceeded hard timeout ceiling; terminate forcefully
                proc.terminate()
                proc.join(timeout=0.2)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=0.2)

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return ExecutionResult(
                    stdout="",
                    stderr=(
                        f"Execution timed out: process terminated after exceeding "
                        f"hard timeout ceiling of {effective_timeout:.1f}s"
                    ),
                    exit_code=124,
                    duration_ms=round(duration_ms, 2),
                )

            # Normal completion: poll pipe for payload
            if parent_conn.poll(0.2):
                payload = parent_conn.recv()
                stdout = payload.get("stdout", "")
                stderr = payload.get("stderr", "")
                exit_code = payload.get("exit_code", 0)
            else:
                stdout = ""
                stderr = f"Process terminated abnormally with exit code {proc.exitcode}"
                exit_code = proc.exitcode if proc.exitcode is not None else 1

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=round(duration_ms, 2),
            )
        finally:
            parent_conn.close()
            with contextlib.suppress(ValueError):
                proc.close()

    # Convenient alias
    run = execute

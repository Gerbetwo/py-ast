"""Unit tests for the isolated process sandboxed code executor."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from py_ast.api.server import app
from py_ast.core.compiler import CompilerPipeline
from py_ast.core.executor import (
    DISALLOWED_BUILTINS,
    ExecuteRequest,
    ExecutionResult,
    SandboxedExecutor,
)


def test_stdout_capture_single_print() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("print('Hello from sandboxed executor!')")

    assert isinstance(result, ExecutionResult)
    assert result.exit_code == 0
    assert result.stdout == "Hello from sandboxed executor!\n"
    assert result.stderr == ""
    assert result.duration_ms >= 0.0


def test_stdout_capture_multiple_prints() -> None:
    executor = SandboxedExecutor()
    code = "print('line 1')\nprint('line 2')\nprint('line 3')\n"
    result = executor.execute(code)

    assert result.exit_code == 0
    assert result.stdout == "line 1\nline 2\nline 3\n"
    assert result.stderr == ""


def test_stdout_capture_end_separator() -> None:
    executor = SandboxedExecutor()
    code = "print('part1', end=' '); print('part2')"
    result = executor.execute(code)

    assert result.exit_code == 0
    assert result.stdout == "part1 part2\n"
    assert result.stderr == ""


def test_safe_builtins_execution() -> None:
    executor = SandboxedExecutor()
    code = (
        "numbers = list(range(4))\n"
        "print('length:', len(numbers))\n"
        "print('int:', int('42'))\n"
        "print('str:', str(100))\n"
        "print('float:', float('3.5'))\n"
        "print('bool:', bool(1), bool(0))\n"
        "d = dict(key='val')\n"
        "print('dict:', d['key'])\n"
    )
    result = executor.execute(code)

    assert result.exit_code == 0
    assert "length: 4" in result.stdout
    assert "int: 42" in result.stdout
    assert "str: 100" in result.stdout
    assert "float: 3.5" in result.stdout
    assert "bool: True False" in result.stdout
    assert "dict: val" in result.stdout
    assert result.stderr == ""


def test_error_handling_zerodivision() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("x = 10 / 0")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "ZeroDivisionError" in result.stderr
    assert "division by zero" in result.stderr


def test_error_handling_syntax_error() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("def invalid_syntax_!#(")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "SyntaxError" in result.stderr


def test_error_handling_name_error() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("print(uninitialized_variable)")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "NameError" in result.stderr
    assert "uninitialized_variable" in result.stderr


def test_error_handling_type_error() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("x = 'text' + 123")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "TypeError" in result.stderr


def test_error_handling_value_error() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("int('invalid_number_literal')")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "ValueError" in result.stderr
    assert "invalid literal for int()" in result.stderr


def test_error_handling_index_error() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("items = list()\nitems[0]")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "IndexError" in result.stderr
    assert "list index out of range" in result.stderr


def test_unauthorized_access_open_blocked() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("open('/etc/passwd', 'r')")

    assert result.exit_code != 0
    assert "NameError" in result.stderr
    assert "open" in result.stderr


def test_unauthorized_access_import_os_blocked() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("import os\nos.system('echo hacked')")

    assert result.exit_code != 0
    assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr


def test_unauthorized_access_import_sys_blocked() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("import sys\nprint(sys.path)")

    assert result.exit_code != 0
    assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr


def test_unauthorized_access_import_subprocess_blocked() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("import subprocess\nsubprocess.run(['ls'])")

    assert result.exit_code != 0
    assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr


def test_unauthorized_access_import_importlib_blocked() -> None:
    executor = SandboxedExecutor()
    result = executor.execute("import importlib\nimportlib.import_module('os')")

    assert result.exit_code != 0
    assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr


def test_unauthorized_access_eval_exec_blocked() -> None:
    executor = SandboxedExecutor()
    result_eval = executor.execute("eval('1 + 1')")
    assert result_eval.exit_code != 0
    assert "NameError" in result_eval.stderr
    assert "eval" in result_eval.stderr

    result_exec = executor.execute("exec('1 + 1')")
    assert result_exec.exit_code != 0
    assert "NameError" in result_exec.stderr
    assert "exec" in result_exec.stderr


def test_safe_builtins_whitelist_integrity() -> None:
    for dangerous in DISALLOWED_BUILTINS:
        assert dangerous not in SandboxedExecutor.SAFE_BUILTINS

    expected_safe = {
        "bool",
        "dict",
        "float",
        "int",
        "len",
        "list",
        "print",
        "range",
        "str",
    }
    for safe in expected_safe:
        assert safe in SandboxedExecutor.SAFE_BUILTINS


def test_process_timeout_termination() -> None:
    executor = SandboxedExecutor()
    start_time = time.perf_counter()
    # Request a short timeout of 0.1s to test timeout termination promptly
    result = executor.execute("while True: pass", timeout=0.1)
    duration_sec = time.perf_counter() - start_time

    assert result.exit_code == 124
    assert result.stdout == ""
    assert "timed out" in result.stderr.lower()
    assert duration_sec < 1.0  # Finished promptly around 0.1s
    assert result.duration_ms >= 50.0


def test_hard_timeout_ceiling_enforcement() -> None:
    # Attempting to set or request timeout exceeding 2.0s is capped to 2.0s
    executor = SandboxedExecutor(timeout=10.0)
    assert executor.default_timeout == SandboxedExecutor.HARD_TIMEOUT_CEILING
    assert executor.default_timeout == 2.0


def test_execute_request_dto_input() -> None:
    executor = SandboxedExecutor()
    req = ExecuteRequest(python_code="print('via dto')")
    result = executor.execute(req)

    assert result.exit_code == 0
    assert result.stdout == "via dto\n"


def test_api_execute_endpoint_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/execute",
        json={"python_code": "val = 42\nprint(f'Computed {val}')"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] == 0
    assert data["stdout"] == "Computed 42\n"
    assert data["stderr"] == ""
    assert data["duration_ms"] >= 0.0


def test_api_execute_endpoint_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/execute",
        json={"python_code": "1 / 0"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] == 1
    assert "ZeroDivisionError" in data["stderr"]


def test_api_execute_endpoint_security_blocked() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/execute",
        json={"python_code": "import os\nos.system('id')"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] != 0
    assert "ImportError" in data["stderr"] or "ModuleNotFoundError" in data["stderr"]


def test_api_execute_endpoint_timeout() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/execute",
        json={"python_code": "while True: pass", "timeout": 0.1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] == 124
    assert "timed out" in data["stderr"].lower()


def test_compiler_pipeline_generated_code_execution() -> None:
    pipeline = CompilerPipeline()
    executor = SandboxedExecutor()

    # Compile user source in compiler pipeline
    code = "var a = 25; var b = 17; print(a + b);"
    compiled = pipeline.compile(code)
    assert not compiled.has_errors
    assert compiled.generated_python != ""

    # Execute generated python code in isolated sandbox
    res = executor.execute(compiled.generated_python)
    assert res.exit_code == 0
    assert res.stdout.strip() == "42"
    assert res.stderr == ""

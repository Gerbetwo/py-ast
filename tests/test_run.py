import sys
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

# Ensure repository root is on sys.path for importing root-level run.py
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import PROJECT_ROOT, main


def test_main_with_uv_default_args() -> None:
    with (
        patch("run.shutil.which", return_value="/usr/local/bin/uv") as mock_which,
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=[], returncode=0)

        exit_code = main([])

        assert exit_code == 0
        mock_which.assert_called_once_with("uv")
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["uv", "sync", "--all-extras", "--dev"],
            check=False,
            cwd=PROJECT_ROOT,
        )
        mock_run.assert_any_call(
            ["uv", "run", "python", "-m", "py_ast.main"],
            check=False,
            cwd=PROJECT_ROOT,
        )


def test_main_with_uv_custom_args() -> None:
    custom_args = ["--web-only", "--host", "0.0.0.0", "--port", "9000"]
    with (
        patch("run.shutil.which", return_value="/usr/bin/uv"),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=[], returncode=0)

        exit_code = main(custom_args)

        assert exit_code == 0
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["uv", "sync", "--all-extras", "--dev"],
            check=False,
            cwd=PROJECT_ROOT,
        )
        mock_run.assert_any_call(
            ["uv", "run", "python", "-m", "py_ast.main", *custom_args],
            check=False,
            cwd=PROJECT_ROOT,
        )


def test_main_without_uv_fallback_pip() -> None:
    expected_python = sys.executable or "python"
    with (
        patch("run.shutil.which", return_value=None) as mock_which,
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=[], returncode=0)

        exit_code = main([])

        assert exit_code == 0
        mock_which.assert_called_once_with("uv")
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            [expected_python, "-m", "pip", "install", "-e", "."],
            check=False,
            cwd=PROJECT_ROOT,
        )
        mock_run.assert_any_call(
            [expected_python, "-m", "py_ast.main"],
            check=False,
            cwd=PROJECT_ROOT,
        )


def test_main_without_uv_custom_args() -> None:
    expected_python = sys.executable or "python"
    custom_args = ["--web-only", "--port", "8080"]
    with (
        patch("run.shutil.which", return_value=None),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=[], returncode=0)

        exit_code = main(custom_args)

        assert exit_code == 0
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            [expected_python, "-m", "pip", "install", "-e", "."],
            check=False,
            cwd=PROJECT_ROOT,
        )
        mock_run.assert_any_call(
            [expected_python, "-m", "py_ast.main", *custom_args],
            check=False,
            cwd=PROJECT_ROOT,
        )


def test_main_sync_failure_with_uv() -> None:
    with (
        patch("run.shutil.which", return_value="/bin/uv"),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=["uv", "sync"], returncode=1)

        exit_code = main([])

        assert exit_code == 1
        # Should NOT run the application if sync failed
        assert mock_run.call_count == 1


def test_main_sync_failure_without_uv() -> None:
    with (
        patch("run.shutil.which", return_value=None),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=["pip", "install"], returncode=2)

        exit_code = main(["--web-only"])

        assert exit_code == 2
        assert mock_run.call_count == 1


def test_main_app_failure_propagates_exit_code() -> None:
    with (
        patch("run.shutil.which", return_value="/usr/bin/uv"),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.side_effect = [
            CompletedProcess(args=["uv", "sync"], returncode=0),
            CompletedProcess(args=["uv", "run"], returncode=42),
        ]

        exit_code = main([])

        assert exit_code == 42
        assert mock_run.call_count == 2


def test_main_keyboard_interrupt_handled() -> None:
    with (
        patch("run.shutil.which", return_value="/usr/bin/uv"),
        patch("run.subprocess.run", side_effect=KeyboardInterrupt),
    ):
        exit_code = main([])
        assert exit_code == 130


def test_main_default_argv_from_sys_argv() -> None:
    with (
        patch.object(sys, "argv", ["run.py", "--web-only"]),
        patch("run.shutil.which", return_value="/usr/bin/uv"),
        patch("run.subprocess.run") as mock_run,
    ):
        mock_run.return_value = CompletedProcess(args=[], returncode=0)

        exit_code = main()

        assert exit_code == 0
        mock_run.assert_any_call(
            ["uv", "run", "python", "-m", "py_ast.main", "--web-only"],
            check=False,
            cwd=PROJECT_ROOT,
        )

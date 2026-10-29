from unittest.mock import MagicMock, patch

from py_ast.api.server import app
from py_ast.main import main, start_server


def test_start_server() -> None:
    with patch("py_ast.main.uvicorn.run") as mock_run:
        start_server(host="127.0.0.1", port=8000)
        mock_run.assert_called_once_with(
            app, host="127.0.0.1", port=8000, log_level="warning"
        )


def test_main_web_only() -> None:
    with (
        patch("py_ast.main.start_server") as mock_start_server,
        patch("py_ast.main.webview.create_window") as mock_create_window,
        patch("py_ast.main.webview.start") as mock_start,
    ):
        main(["--web-only"])
        mock_start_server.assert_called_once_with(host="127.0.0.1", port=8000)
        mock_create_window.assert_not_called()
        mock_start.assert_not_called()


def test_main_web_only_custom_host_and_port() -> None:
    with (
        patch("py_ast.main.start_server") as mock_start_server,
        patch("py_ast.main.webview.create_window") as mock_create_window,
        patch("py_ast.main.webview.start") as mock_start,
    ):
        main(["--web-only", "--host", "0.0.0.0", "--port", "9090"])
        mock_start_server.assert_called_once_with(host="0.0.0.0", port=9090)
        mock_create_window.assert_not_called()
        mock_start.assert_not_called()


def test_main_desktop_mode() -> None:
    with (
        patch("py_ast.main.Thread") as mock_thread_cls,
        patch("py_ast.main.webview.create_window") as mock_create_window,
        patch("py_ast.main.webview.start") as mock_start,
    ):
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        main([])

        mock_thread_cls.assert_called_once_with(
            target=start_server,
            args=("127.0.0.1", 8000),
            daemon=True,
        )
        mock_thread_instance.start.assert_called_once()
        mock_create_window.assert_called_once_with(
            title="py-ast | Compiler & AST Visualizer",
            url="http://127.0.0.1:8000",
            width=1200,
            height=800,
        )
        mock_start.assert_called_once()

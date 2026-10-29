import argparse
import os
import sys
from threading import Thread

import uvicorn
import webview

from py_ast.api.server import app


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the Uvicorn FastAPI server."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main(argv: list[str] | None = None) -> None:
    """Application entry point supporting dual Web / Desktop runtime modes."""
    parser = argparse.ArgumentParser(
        description="py-ast | Educational Compiler & AST Visualizer",
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="Launch standard Uvicorn FastAPI server without desktop window",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "127.0.0.1"),
        help="Server bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Server bind port (default: 8000)",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.web_only:
        print(f"🌐 Starting py-ast Web Server on http://{args.host}:{args.port}")
        start_server(host=args.host, port=args.port)
    else:
        print(f"🖥️ Starting py-ast Desktop Window on http://{args.host}:{args.port}...")
        server_thread = Thread(
            target=start_server,
            args=(args.host, args.port),
            daemon=True,
        )
        server_thread.start()

        webview.create_window(
            title="py-ast | Compiler & AST Visualizer",
            url=f"http://{args.host}:{args.port}",
            width=1200,
            height=800,
        )
        webview.start()


if __name__ == "__main__":
    main()

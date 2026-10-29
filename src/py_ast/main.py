import sys
from threading import Thread

import uvicorn
import webview

from py_ast.api.server import app


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


def main():
    if "--web-only" in sys.argv:
        print("🌐 Starting py-ast Web Server on http://127.0.0.1:8000")
        start_server()
    else:
        print("🖥️ Starting py-ast Desktop Window...")
        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()

        webview.create_window(
            title="py-ast | Compiler & AST Visualizer",
            url="http://127.0.0.1:8000/docs",
            width=1200,
            height=800,
        )
        webview.start()


if __name__ == "__main__":
    main()

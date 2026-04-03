from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
LATEST_DIR = ROOT_DIR / "output" / "latest"


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the latest visual analytics report.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not LATEST_DIR.exists():
        raise FileNotFoundError(
            f"Не найдена папка {LATEST_DIR}. Сначала запустите user_tests/build_visual_report.py."
        )

    handler = partial(SimpleHTTPRequestHandler, directory=str(LATEST_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Visual report is available at http://127.0.0.1:{args.port}/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

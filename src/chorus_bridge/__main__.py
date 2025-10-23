from __future__ import annotations

import uvicorn

from .app import create_app


def main() -> None:  # pragma: no cover - entry point
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":  # pragma: no cover
    main()

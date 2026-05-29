from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.bookbinder4.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=env,
    )
    frontend = subprocess.Popen(["npm", "run", "dev"], cwd=ROOT / "frontend")
    print("Bookbinder 4 backend:  http://127.0.0.1:8000")
    print("Bookbinder 4 frontend: http://127.0.0.1:5173")
    try:
        while True:
            code = backend.poll()
            if code is not None:
                return code
            code = frontend.poll()
            if code is not None:
                return code
            signal.pause()
    except KeyboardInterrupt:
        return 0
    finally:
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())

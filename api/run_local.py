"""Run the PostgreSQL API and Vite development server together on Windows/macOS/Linux."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT)
    if sys.platform == "win32":
        frontend = subprocess.Popen("npm.cmd --prefix frontend run dev", cwd=ROOT, shell=True)
    else:
        frontend = subprocess.Popen(["npm", "--prefix", "frontend", "run", "dev"], cwd=ROOT)
    print("\nDashboard: http://127.0.0.1:5173  |  API: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both servers.\n", flush=True)
    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(.5)
        return backend.returncode or frontend.returncode or 0
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (frontend, backend):
            if process.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    process.terminate()
        for process in (frontend, backend):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())

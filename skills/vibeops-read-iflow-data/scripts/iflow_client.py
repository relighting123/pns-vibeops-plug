"""Service-specific entrypoint; shared imports resolve from the installed plugin root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "python"))
from http_client.cli import main

if __name__ == "__main__":
    sys.exit(main("iflow", "read"))

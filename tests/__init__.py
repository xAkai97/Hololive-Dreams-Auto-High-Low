import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

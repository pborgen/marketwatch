import sys
from pathlib import Path

_APP = str(Path(__file__).resolve().parents[1])
if _APP not in sys.path:
    sys.path.insert(0, _APP)

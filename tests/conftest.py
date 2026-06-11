"""Pytest bootstrap — put the project's ``src/`` on the import path.

Works regardless of the directory pytest is invoked from (root or project), so
``import synthobs`` resolves to ``projects/working/SynthOBS/src/synthobs``.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

"""Pytest bootstrap — put the project's ``src/`` on the import path.

Works regardless of the directory pytest is invoked from (root or project), so
``import synthobs`` resolves to the checkout's ``src/synthobs`` directory; in the
template integration the project is additionally available through the
``projects/working/SynthOBS`` symlink.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

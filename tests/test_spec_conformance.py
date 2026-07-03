"""docs/spec/metrics.yaml and metrics_table.md are GENERATED from the code
registry (scripts/gen_spec.py) — there is no longer a hand-authored copy to
drift out of sync with. This just checks nobody edited the registry without
regenerating the checked-in docs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def test_generated_docs_are_fresh():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_spec.py"), "--check"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 0, (
        "docs/spec/metrics.yaml or metrics_table.md is stale — run `python scripts/gen_spec.py`:\n"
        f"{result.stdout}{result.stderr}"
    )

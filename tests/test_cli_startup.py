"""CLI-01 gate: importing the CLI must not pull the heavy scrape graph.

`fc26 --help` and light commands (search/show/list) should start fast. The
scrape parsers (selectolax) and HTTP client (httpx) are deferred into the
command bodies that use them, so a bare `import fc26.cli` must NOT load them.
Run in a subprocess so other tests that already imported selectolax/httpx don't
pollute this process's sys.modules.
"""

from __future__ import annotations

import subprocess
import sys


def test_cli_import_does_not_pull_heavy_deps():
    code = (
        "import sys, fc26.cli; "
        "heavy = {'selectolax', 'httpx'} & set(sys.modules); "
        "assert not heavy, f'cli import pulled heavy deps: {heavy}'"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

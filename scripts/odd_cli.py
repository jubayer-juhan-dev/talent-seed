"""Run the `open-dev-data` CLI (v1.4) with a compatibility shim.

open-dev-data 1.4 passes `socket_options=` to aiohttp.TCPConnector, which no released
aiohttp (checked 3.12.15 - 3.14.3) accepts, so `download` crashes before fetching
anything. This wrapper drops that one kwarg and otherwise runs the CLI unchanged
(same download, Range-resume and blake3 verification code).

Usage: uv run --with open-dev-data==1.4 scripts/odd_cli.py download -o ./raw_open_dev_data --resume
"""

import inspect
import sys

import aiohttp

_orig_init = aiohttp.TCPConnector.__init__
if "socket_options" not in inspect.signature(_orig_init).parameters:

    def _init(self, *args, socket_options=None, **kwargs):
        _orig_init(self, *args, **kwargs)

    aiohttp.TCPConnector.__init__ = _init

from open_dev_data.commands import main  # noqa: E402

if __name__ == "__main__":
    sys.argv[0] = "open-dev-data"
    sys.exit(main())

"""Thin entrypoint: the YCSB-specific adapter lives in ``tools/ycsb_bench``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ycsb_bench import main

if __name__ == "__main__":
    raise SystemExit(main())

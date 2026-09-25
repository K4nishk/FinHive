"""`python -m loan_manager.infrastructure.seed --db data/demo.db`"""

from __future__ import annotations

import sys

from loan_manager.infrastructure.seed.demo_seed import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

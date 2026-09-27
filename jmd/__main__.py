# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import sys

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from jmd.selftest import main
    else:
        from jmd.app import main
    sys.exit(main())

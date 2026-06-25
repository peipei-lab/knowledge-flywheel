#!/usr/bin/env python3
"""Initialize local identity files from public templates."""

from __future__ import annotations

import argparse
from identity_context import CONTENT_IDENTITY, init_identity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing local identity files.")
    args = parser.parse_args()

    written = init_identity(overwrite=args.overwrite)
    if written:
        for path in written:
            print(f"Wrote {path}")
    else:
        print(f"Identity files already exist in {CONTENT_IDENTITY}")
    print(f"Edit local identity files here: {CONTENT_IDENTITY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

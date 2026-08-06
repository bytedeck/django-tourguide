#!/usr/bin/env python
"""Entry point for the demo project.

The demo is a real, runnable Django site. It is what package changes get demonstrated and
screenshotted against, since the package itself has no user interface of its own.
"""

import os
import sys
from pathlib import Path


def main():
    """Run a management command against the demo project."""
    # Put the package's `src/` on the path so the demo runs straight from a checkout, with no
    # install step needed before `runserver`.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demosite.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

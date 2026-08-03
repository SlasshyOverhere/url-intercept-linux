import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from linux_url_interceptor import cli
else:
    from . import cli

if __name__ == "__main__":
    sys.exit(cli.main())

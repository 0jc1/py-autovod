#!/usr/bin/env python3

import sys
from .main import main

if __name__ == "__main__":
    if sys.version_info < (3, 10):
        print("Error: Python 3.10 or higher is required")
        print("Current Python version: " + sys.version)
        sys.exit(1)
    
    sys.exit(main())
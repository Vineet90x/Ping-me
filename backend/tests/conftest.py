import os
import sys

# Ensure the backend root is importable when running `pytest` from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

"""
Streamlit Cloud entry point.

This file must be at the repo root for Streamlit Community Cloud to find it.
All real dashboard code is in src/fir_qa/dashboard.py.
"""

import sys
from pathlib import Path

# Make src/ importable when Streamlit Cloud runs this file directly
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fir_qa.dashboard import main

if __name__ == "__main__":
    main()

import pytest
import os
import sys
from pathlib import Path

# Add src to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def project_root():
    """Return the project root directory"""
    return Path(__file__).parent.parent

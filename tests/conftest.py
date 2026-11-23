import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
ROOT_DIR = TESTS_DIR.parent

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(ROOT_DIR))

"""pytest 全域設定"""
import sys
from pathlib import Path

# 確保 src/ 在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

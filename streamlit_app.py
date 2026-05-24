"""
Streamlit Cloud 入口（指向此檔案）
本機開發：streamlit run streamlit_app.py
Streamlit Cloud 設定：Main file path = streamlit_app.py
"""
import sys
from pathlib import Path

# 確保 project root 在 Python path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 載入 .env（本機用；Streamlit Cloud 用 st.secrets）
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# 執行 Dashboard
from src.dashboard.app import *  # noqa: F401, F403

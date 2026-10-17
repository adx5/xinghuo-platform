import os
from pathlib import Path
from dotenv import load_dotenv

# 显式定位项目根目录下的 .env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.7"))
MAX_MATCH_ROUNDS = int(os.getenv("MAX_MATCH_ROUNDS", "2"))

# 新增 Mock 模式开关
MOCK_MODE = os.getenv("MOCK_MODE", "False").lower() in ("true", "1", "yes")
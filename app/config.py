import os
from pathlib import Path
from dotenv import load_dotenv

# 尝试加载本地 .env（如果存在的话）
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)

# 读取环境变量（云端会直接从这里读取到仪表板配置的值）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.7"))
MAX_MATCH_ROUNDS = int(os.getenv("MAX_MATCH_ROUNDS", "2"))
MOCK_MODE = os.getenv("MOCK_MODE", "False").lower() in ("true", "1", "yes")
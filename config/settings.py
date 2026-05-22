import os
from dotenv import load_dotenv

load_dotenv()

# ── Base de datos ──────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "3306")
DB_NAME     = os.getenv("DB_NAME", "contable_db")
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "juan2054")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# ── Aplicación ─────────────────────────────────────────────────
APP_NAME    = os.getenv("APP_NAME", "SistemaContable")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV     = os.getenv("APP_ENV", "development")

# ── Seguridad ──────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "dev_key_insegura")

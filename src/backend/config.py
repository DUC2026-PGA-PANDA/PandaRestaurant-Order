import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'data', 'panda.db'))

os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)

class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
    GROUP_CHAT_ID = os.environ.get('GROUP_CHAT_ID', '')
    BOT_USERNAME = os.environ.get('BOT_USERNAME', '')
    DATABASE_PATH = os.path.abspath(os.path.expanduser(os.environ.get('DATABASE_PATH', DEFAULT_DB_PATH)))
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_SUCCESS_URL = os.environ.get('STRIPE_SUCCESS_URL', '')
    STRIPE_CANCEL_URL = os.environ.get('STRIPE_CANCEL_URL', '')

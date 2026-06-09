from dotenv import load_dotenv

# Load .env before importing the app so ANTHROPIC_API_KEY is available.
load_dotenv()

from web.app import app

# uvicorn main:app --reload picks up this object.

"""Entry point for uvicorn — run with: uvicorn server:app --port 8085"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from app.main import app  # noqa: F401

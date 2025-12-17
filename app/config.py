
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", os.path.join(BASE_DIR, "..", "exports"))
os.makedirs(EXPORT_FOLDER, exist_ok=True)

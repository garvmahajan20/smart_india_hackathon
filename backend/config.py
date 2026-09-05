# -*- coding: utf-8 -*-
import os

def load_dotenv(env_path: str = ".env") -> bool:
    """
    Loads environment variables from a local .env file into os.environ.
    Preserves existing process environment variables.
    """
    if not os.path.exists(env_path):
        return False

    try:
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.lstrip("\ufeff").strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        return True
    except Exception:
        return False

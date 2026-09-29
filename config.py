"""
Configuration module — loads secrets from .env and provides constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys & Secrets ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")
LEETCODE_CSRF_TOKEN = os.getenv("LEETCODE_CSRF_TOKEN")

# --- LeetCode Settings ---
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

GEMINI_MODEL = "gemini-3-flash-preview"

# --- Agent Settings ---
MAX_RETRIES = 3
SOLUTIONS_DIR = "solutions"

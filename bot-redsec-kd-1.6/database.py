import json
import os
from config import DATA_DIR, DATA_FILE

# ================== USERS ==================

def load_users() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar users.json: {e}")
        return {}


def save_users(users: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ================== TOP5 ==================

TOP5_FILE = os.path.join(DATA_DIR, "top5.json")

def load_top5() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TOP5_FILE):
        return {"squad": [], "duo": [], "solo": [], "gauntlet": []}
    try:
        with open(TOP5_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar top5.json: {e}")
        return {"squad": [], "duo": [], "solo": [], "gauntlet": []}


def save_top5(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOP5_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

import os
import json
import sqlite3
import requests

class DataIngestor:
    def __init__(self, db_path: str = "data/wf_database.sqlite", raw_dir: str = "data/raw_wfcd") -> None:
        self.db_path = db_path
        self.raw_dir = raw_dir
        self.categories = ["Primary", "Secondary", "Melee", "Mods", "Warframes"]

    def init_database(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weapons (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                rarity TEXT,
                UNIQUE(name)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mods (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                rarity TEXT,
                UNIQUE(name)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warframes (
                id TEXT PRIMARY KEY,
                name TEXT,
                rarity TEXT,
                UNIQUE(name)
            )
        ''')

        conn.commit()
        conn.close()

    def download_wfcd_data(self, category: str) -> list:
        filename = f"{category.capitalize()}.json"
        cache_file = os.path.join(self.raw_dir, filename)
        if not os.path.exists(self.raw_dir):
            os.makedirs(self.raw_dir, exist_ok=True)

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        url = f"https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/{filename}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                return data
        except Exception as e:
            print(f"[WARN] Failed to fetch {category}: {e}")
        return []

    def seed_builtin_samples(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        weapons = [
            {"id": "Torid", "name": "Torid", "type": "Pistol", "rarity": "Common"},
            {"id": "Laetum", "name": "Laetum", "type": "Pistol", "rarity": "Common"},
            {"id": "Phenmor", "name": "Phenmor", "type": "Pistol", "rarity": "Common"},
            {"id": "MK1-Braton", "name": "MK1-Braton", "type": "Rifle", "rarity": "Common"},
            {"id": "Nova", "name": "Nova", "type": "Rifle", "rarity": "Common"},
            {"id": "Mesa", "name": "Mesa", "type": "Rifle", "rarity": "Common"},
            {"id": "Revenant", "name": "Revenant", "type": "Rifle", "rarity": "Common"}
        ]

        mods = [
            {"id": "Serration", "name": "Serration", "type": "Barrel", "rarity": "Common"},
            {"id": "Galvanized Chamber", "name": "Galvanized Chamber", "type": "Receiver", "rarity": "Common"},
            {"id": "Critical Delay", "name": "Critical Delay", "type": "Stock", "rarity": "Common"},
            {"id": "Vital Sense", "name": "Vital Sense", "type": "Scope", "rarity": "Common"},
            {"id": "Hunter Munitions", "name": "Hunter Munitions", "type": "Barrel", "rarity": "Common"},
            {"id": "Malignant Force", "name": "Malignant Force", "type": "Receiver", "rarity": "Common"},
            {"id": "Rime Rounds", "name": "Rime Rounds", "type": "Stock", "rarity": "Common"},
            {"id": "Primed Firestorm", "name": "Primed Firestorm", "type": "Scope", "rarity": "Common"},
            {"id": "Catalyzing Shields", "name": "Catalyzing Shields", "type": "Barrel", "rarity": "Common"},
            {"id": "Adaptation", "name": "Adaptation", "type": "Receiver", "rarity": "Common"}
        ]

        warframes = [
            {"id": "Trinity", "name": "Trinity", "rarity": "Common"},
            {"id": "Rhino", "name": "Rhino", "rarity": "Common"},
            {"id": "Volt", "name": "Volt", "rarity": "Common"}
        ]

        cursor.executemany("INSERT OR IGNORE INTO weapons (id, name, type, rarity) VALUES (?, ?, ?, ?)", [(w['id'], w['name'], w.get('type', ''), w['rarity']) for w in weapons])
        cursor.executemany("INSERT OR IGNORE INTO mods (id, name, type, rarity) VALUES (?, ?, ?, ?)", [(m['id'], m['name'], m.get('type', ''), m['rarity']) for m in mods])
        cursor.executemany("INSERT OR IGNORE INTO warframes (id, name, rarity) VALUES (?, ?, ?)", [(wf['id'], wf['name'], wf['rarity']) for wf in warframes])

        conn.commit()
        conn.close()

    def ingest_all(self, use_remote: bool = False) -> None:
        self.init_database()
        self.seed_builtin_samples()

        for category in self.categories:
            data = self.download_wfcd_data(category) if use_remote else self.download_wfcd_data(category)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if category in ("Primary", "Secondary", "Melee"):
                cursor.executemany("INSERT OR IGNORE INTO weapons (id, name, type, rarity) VALUES (?, ?, ?, ?)", [(item.get('uniqueName', item.get('name', '')), item.get('name', ''), item.get('type', category), item.get('rarity', 'Common')) for item in data if isinstance(item, dict)])
            elif category == "Mods":
                cursor.executemany("INSERT OR IGNORE INTO mods (id, name, type, rarity) VALUES (?, ?, ?, ?)", [(item.get('uniqueName', item.get('name', '')), item.get('name', ''), item.get('type', ''), item.get('rarity', 'Common')) for item in data if isinstance(item, dict)])
            elif category == "Warframes":
                cursor.executemany("INSERT OR IGNORE INTO warframes (id, name, rarity) VALUES (?, ?, ?)", [(item.get('uniqueName', item.get('name', '')), item.get('name', ''), item.get('rarity', 'Common')) for item in data if isinstance(item, dict)])

            conn.commit()
            conn.close()

if __name__ == "__main__":
    DataIngestor().ingest_all()
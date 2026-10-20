import os
import requests
import time
from pydantic import BaseModel

class WikiIngestor:
    CORE_PAGES = ['Damage', 'Critical_Hit', 'Status_Effect', 'Armor', 'Damage_Attenuation', 'Shield']
    API_URL = 'https://wiki.warframe.com/api.php'

    def __init__(self, output_dir='rules/wiki_docs'):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def fetch_page(self, title):
        params = {
            'action': 'parse',
            'page': title,
            'format': 'json',
            'prop': 'wikitext|revid'
        }
        response = requests.get(self.API_URL, params=params, headers={'User-Agent': 'WarframeOptimizer/1.0'})
        response.raise_for_status()
        data = response.json()
        parse_data = data.get('parse', {})
        text = parse_data.get('wikitext', {}).get('*', '')
        revision_id = parse_data.get('revid', 'latest')
        return text, revision_id

    def fetch_all_core_pages(self):
        for page in self.CORE_PAGES:
            try:
                text, revision_id = self.fetch_page(page)
                self.save_page(page, text, revision_id)
                time.sleep(0.5)  # Gentle rate limit
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch {page}: {e}")

    def save_page(self, title, text, revision_id):
        filename = os.path.join(self.output_dir, f"{title}_{revision_id}.txt")
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"Saved {title} with revision ID {revision_id}")

# Example usage:

    def fetch_all_category_pages(self):
        categories = {
            "mechanics": ["Damage", "Critical_Hit", "Status_Effect", "Armor", "Damage_Attenuation", "Shield", "Overguard"],
            "factions_and_enemies": ["Grineer", "Corpus", "Infested", "Murmur", "Sentient", "Eximus", "Acolyte"],
            "bosses": ["Eidolon_Teralyst", "Profit-Taker_Orb", "Exploiter_Orb", "Ropalolyst", "Archon_Hunt", "Archon_Amar", "Archon_Boreal", "Archon_Nira", "Kuva_Lich", "The_Fragmented"],
            "quests_and_story": ["Quest", "The_Second_Dream", "The_War_Within", "The_Sacrifice", "The_New_War", "Whispers_in_the_Walls"]
        }
        for cat, pages in categories.items():
            cat_dir = os.path.join(self.output_dir, cat)
            if not os.path.exists(cat_dir):
                os.makedirs(cat_dir)
            for page in pages:
                try:
                    text, rev_id = self.fetch_page(page)
                    fpath = os.path.join(cat_dir, f"{page}_{rev_id}.txt")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(text)
                    print(f"[{cat}] Saved {page} (Rev: {rev_id})")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[{cat}] Failed {page}: {e}")

if __name__ == "__main__":
    ingestor = WikiIngestor()
    ingestor.fetch_all_core_pages()
import os
import requests
from pydantic import BaseModel

class CodexSheetImporter:
    SHEET_ID = '1kyA-h2bTLZ2JpOnUMgiB16EE-a9xNrGU0pUgukpPdsU'
    TABS = {
        'gunco': '1116775336',
        'wf_builds': '668839498',
        'companion': '2070403418',
        'content': '1483385200',
        'farming': '212730884',
        'materials': '1568730474',
        'newbie': '1064585601',
        'riven': '299773144'
    }

    def __init__(self, data_dir='data/raw_sheets'):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def fetch_tab(self, tab_key):
        if tab_key not in self.TABS:
            raise ValueError(f"Invalid tab key: {tab_key}")
        gid = self.TABS[tab_key]
        url = f"https://docs.google.com/spreadsheets/export?id={self.SHEET_ID}&gid={gid}&format=csv"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch tab {tab_key}: {response.status_code}")
        file_path = os.path.join(self.data_dir, f"{tab_key}.csv")
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return file_path

    def fetch_all(self):
        for tab_key in self.TABS:
            self.fetch_tab(tab_key)

    def parse_gunco_table(self):
        file_path = os.path.join(self.data_dir, 'gunco.csv')
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Gunco CSV file not found: {file_path}")
        with open(file_path, 'r') as f:
            lines = f.readlines()
        # Assuming the first line is the header
        header = lines[0].strip().split(',')
        data = []
        for line in lines[1:]:
            row = line.strip().split(',')
            data.append(dict(zip(header, row)))
        return data

# Example usage
if __name__ == "__main__":
    importer = CodexSheetImporter()
    importer.fetch_all()
    gunco_data = importer.parse_gunco_table()
    print(gunco_data)
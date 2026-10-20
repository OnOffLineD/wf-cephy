from scripts.wf_data_indexer import WFDataIndexer
import os

idx = WFDataIndexer()
print("data_dir:", idx.data_dir)
print("weapon_arcanes.json exists:", os.path.exists(os.path.join(idx.data_dir, "weapon_arcanes.json")))
matches = [k for k in idx.mods_index.keys() if '인플루언스' in k or 'influence' in k]
print("Matches in mods_index:", matches)

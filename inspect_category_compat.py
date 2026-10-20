from scripts.wf_data_indexer import WFDataIndexer

idx = WFDataIndexer()
m1 = idx.mods_index.get("reaping spiral")
m2 = idx.mods_index.get("volatile quick return")

print("Reaping Spiral:", m1.get('type'), "| compatName:", m1.get('compatName'))
print("Volatile Quick Return:", m2.get('type'), "| compatName:", m2.get('compatName'))

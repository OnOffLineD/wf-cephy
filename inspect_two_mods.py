from scripts.wf_data_indexer import WFDataIndexer

idx = WFDataIndexer()

for target in ["reaping spiral", "volatile quick return", "리핑 스파이럴", "볼래틸 퀵 리턴", "스파이럴", "볼래틸"]:
    matches = [k for k in idx.mods_index.keys() if target in k]
    print(f"Target '{target}' in mods_index: {matches}")

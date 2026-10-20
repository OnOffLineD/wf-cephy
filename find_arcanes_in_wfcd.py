import os

data_dir = "data/raw_wfcd"
for f in os.listdir(data_dir):
    if f.endswith('.json'):
        p = os.path.join(data_dir, f)
        try:
            with open(p, 'r', encoding='utf-8') as fl:
                content = fl.read()
                if "Melee Influence" in content or "Primary Merciless" in content or "Primary Deadhead" in content:
                    print(f"Found in {f}")
        except Exception as e:
            pass

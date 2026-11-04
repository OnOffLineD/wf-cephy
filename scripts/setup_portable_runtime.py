import os
import shutil
from pathlib import Path

def setup_runtime():
    source_dir = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "lib" / "ollama"
    project_root = Path(__file__).resolve().parent.parent
    target_bin = project_root / "bin"
    target_models = project_root / "models"

    target_bin.mkdir(parents=True, exist_ok=True)
    target_models.mkdir(parents=True, exist_ok=True)

    print(f"[1/2] Copying llama-server and runtime DLLs (approx 39MB)...")
    for item in source_dir.iterdir():
        if item.is_file() and (item.suffix.lower() == ".dll" or item.name.lower() == "llama-server.exe"):
            dest_file = target_bin / item.name
            if not dest_file.exists():
                print(f"  Copying: {item.name}")
                shutil.copy2(item, dest_file)
            else:
                print(f"  Already exists: {item.name}")

    print("[OK] Runtime bin setup complete!")

if __name__ == "__main__":
    setup_runtime()

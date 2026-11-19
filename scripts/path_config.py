import json
import os
import sys
import tempfile
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def get_path(*parts):
    """Return the absolute path by joining ROOT_DIR with the given parts."""
    return os.path.abspath(os.path.join(ROOT_DIR, *parts))

def get_user_data_path(*parts):
    """Return a path for user-owned state. WF_USER_DATA_DIR overrides data/, so tests stay away from real data."""
    base = os.environ.get('WF_USER_DATA_DIR') or os.path.join(ROOT_DIR, 'data')
    return os.path.abspath(os.path.join(base, *parts))

REPLACE_RETRIES = 5


def write_json_atomic(path, data):
    """Write then swap, so a crash mid-save can't leave a half-written file.

    Each call gets its own temp file: two threads saving the same file must not write into one shared ".tmp".
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows refuses to replace a file another save (or a sync client) has open for a moment.
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

class PathConfig:
    ROOT_DIR = ROOT_DIR
    get_path = staticmethod(get_path)
    
    DATA_DIR = get_path('data')
    MODELS_DIR = get_path('models')
    BIN_DIR = get_path('bin')
    RULES_DIR = get_path('rules')
    ASSETS_DIR = get_path('assets')

# Example usage
if __name__ == "__main__":
    print("ROOT_DIR:", PathConfig.ROOT_DIR)
    print("DATA_DIR:", PathConfig.DATA_DIR)
    print("MODELS_DIR:", PathConfig.MODELS_DIR)
    print("BIN_DIR:", PathConfig.BIN_DIR)
    print("RULES_DIR:", PathConfig.RULES_DIR)
    print("ASSETS_DIR:", PathConfig.ASSETS_DIR)
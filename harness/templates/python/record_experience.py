"""
Experience Recorder (Python)
Appends structured troubleshooting entries to EXPERIENCE.md
"""
import sys
import os
import re
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXP_FILE = os.path.join(ROOT_DIR, "EXPERIENCE.md")

def append_experience(title: str, symptom: str, solution: str, lesson: str):
    if not os.path.exists(EXP_FILE):
        print(f"Error: {EXP_FILE} does not exist.")
        sys.exit(1)
        
    with open(EXP_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    matches = re.findall(r"EXP-(\d+)", content)
    next_id = f"EXP-{int(matches[-1]) + 1:03d}" if matches else "EXP-001"

    entry = f"""
---

### {next_id}: {title}
- **기록일자**: {datetime.now().strftime('%Y-%m-%d')}
- **현상**: {symptom}
- **해결책**:
  - {solution}
- **교훈**: {lesson}
"""
    with open(EXP_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"[EXPERIENCE] Successfully recorded {next_id}: {title}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python scripts/record_experience.py <title> <symptom> <solution> <lesson>")
        sys.exit(1)
    append_experience(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

/**
 * Experience Recorder (Node.js)
 * Appends structured troubleshooting entries to EXPERIENCE.md
 */
import { existsSync, readFileSync, appendFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const ROOT_DIR = resolve(dirname(__filename), '..');
const EXP_FILE = resolve(ROOT_DIR, 'EXPERIENCE.md');

const args = process.argv.slice(2);
if (args.length < 4) {
  console.log('Usage: node scripts/record_experience.mjs <title> <symptom> <solution> <lesson>');
  process.exit(1);
}

const [title, symptom, solution, lesson] = args;

if (!existsSync(EXP_FILE)) {
  console.error(`Error: ${EXP_FILE} does not exist.`);
  process.exit(1);
}

const content = readFileSync(EXP_FILE, 'utf-8');
const matches = [...content.matchAll(/EXP-(\d+)/g)];
const lastNum = matches.length > 0 ? parseInt(matches[matches.length - 1][1], 10) : 0;
const nextId = `EXP-${String(lastNum + 1).padStart(3, '0')}`;
const today = new Date().toISOString().slice(0, 10);

const entry = `
---

### ${nextId}: ${title}
- **기록일자**: ${today}
- **현상**: ${symptom}
- **해결책**:
  - ${solution}
- **교훈**: ${lesson}
`;

appendFileSync(EXP_FILE, entry, 'utf-8');
console.log(`[EXPERIENCE] Successfully recorded ${nextId}: ${title}`);

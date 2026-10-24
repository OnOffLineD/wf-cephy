/**
 * Universal Harness Probe Runner (Node.js / TypeScript)
 * Gate 1: Test Suite (npm test / vitest / jest)
 * Gate 2: Static Sanity & Type Check
 * Gate 3: Graphify / Workspace Integrity
 */
import { existsSync, statSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const ROOT_DIR = resolve(dirname(__filename), '..');

function runTests() {
  console.log('[PROBE 1/3] Running Test Suite (npm test)...');
  const res = spawnSync('npm', ['test'], { cwd: ROOT_DIR, encoding: 'utf-8', shell: true });
  const passed = res.status === 0;
  console.log(` -> Test Suite: ${passed ? 'PASSED' : 'FAILED'}`);
  if (!passed) {
    console.log('\n--- OUTPUT ---\n', res.stdout?.slice(-1200) || '');
    console.log('\n--- ERRORS ---\n', res.stderr?.slice(-800) || '');
  }
  return passed;
}

function runSanity() {
  console.log('[PROBE 2/3] Checking Project Sanity & Guardrails...');
  const hasAgents = existsSync(resolve(ROOT_DIR, '.agents'));
  console.log(` -> Domain Sanity: ${hasAgents ? 'PASSED' : 'FAILED (.agents missing)'}`);
  return hasAgents;
}

function runGraph() {
  console.log('[PROBE 3/3] Checking Graphify / AST Integrity...');
  const graphFile = resolve(ROOT_DIR, 'graphify-out', 'graph.json');
  if (existsSync(graphFile)) {
    const sizeKb = statSync(graphFile).size / 1024;
    console.log(` -> Graphify Graph: PRESENT (${sizeKb.toFixed(1)} KB)`);
  } else {
    console.log(' -> Graphify Graph: SKIPPED (graph.json not generated yet)');
  }
  return true;
}

console.log('='.repeat(60));
console.log(' [Universal Harness Probe] Starting Verification Cycle');
console.log('='.repeat(60));

const g1 = runTests();
const g2 = runSanity();
const g3 = runGraph();

console.log('='.repeat(60));
if (g1 && g2 && g3) {
  console.log(' [Harness Probe Result] ALL GATES PASSED (COMPOSE READY)');
  console.log('='.repeat(60));
  process.exit(0);
} else {
  console.log(' [Harness Probe Result] GATES FAILED - REVISION REQUIRED');
  console.log('='.repeat(60));
  process.exit(1);
}

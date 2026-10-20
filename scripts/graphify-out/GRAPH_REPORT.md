# Graph Report - scripts  (2026-10-14)

## Corpus Check
- 26 files · ~12,393 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 237 nodes · 423 edges · 15 communities (6 shown, 9 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 29 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- LocalPipelineRunner
- app_server.py
- OptimizerEngine
- desktop_companion.py
- os
- advanced_mechanics_optimizer.py
- optimizer_engine.py
- LLMOrchestrator
- DesktopPet
- SurvivalEvaluator
- sqlite3
- DataIngestor
- RivenOCRAnalyzer
- WikiIngestor

## God Nodes (most connected - your core abstractions)
1. `LocalPipelineRunner` - 19 edges
2. `OptimizerEngine` - 17 edges
3. `OrdisCompanionApp` - 10 edges
4. `LLMOrchestrator` - 10 edges
5. `OptimizerRequest` - 10 edges
6. `WeaponStats` - 9 edges
7. `ModConfig` - 9 edges
8. `DesktopPet` - 9 edges
9. `DamageSimulator` - 8 edges
10. `ScreenSnipper` - 8 edges

## Surprising Connections (you probably didn't know these)
- `OptimizerHTTPHandler` --uses--> `LLMOrchestrator`  [INFERRED]
  scripts/app_server.py → scripts/llm_orchestrator.py
- `LLMOrchestrator` --uses--> `OptimizerEngine`  [INFERRED]
  scripts/llm_orchestrator.py → scripts/optimizer_engine.py
- `OptimizerRequest` --uses--> `WarframeModConfig`  [INFERRED]
  scripts/optimizer_engine.py → scripts/survival_evaluator.py
- `OptimizerRequest` --uses--> `WarframeStats`  [INFERRED]
  scripts/optimizer_engine.py → scripts/survival_evaluator.py
- `OptimizerEngine` --uses--> `SurvivalEvaluator`  [INFERRED]
  scripts/optimizer_engine.py → scripts/survival_evaluator.py

## Import Cycles
- None detected.

## Communities (15 total, 9 thin omitted)

### Community 1 - "app_server.py"
Cohesion: 0.10
Nodes (6): OptimizerHTTPHandler, run_server(), start_llama_server(), copy_model(), copy_cuda(), setup_runtime()

### Community 2 - "OptimizerEngine"
Cohesion: 0.17
Nodes (7): CombatState, DamageSimulator, ModConfig, WeaponStats, OptimizerEngine, OptimizerRequest, SynergyPlanner

### Community 3 - "desktop_companion.py"
Cohesion: 0.09
Nodes (5): LLMOrchestrator, OrdisCompanionApp, RivenOCRAnalyzer, ScreenSnipper, WorldStateTracker

### Community 4 - "os"
Cohesion: 0.14
Nodes (3): CodexSheetImporter, test_api(), WorldStateTracker

### Community 5 - "advanced_mechanics_optimizer.py"
Cohesion: 0.15
Nodes (5): AdvancedMechanicsOptimizer, EnemyArchetype, IncarnonPerkProfile, OptimizationEngineError, ProgenitorElement

### Community 9 - "SurvivalEvaluator"
Cohesion: 0.54
Nodes (3): SurvivalEvaluator, WarframeModConfig, WarframeStats

## Knowledge Gaps
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LocalPipelineRunner` connect `LocalPipelineRunner` to `app_server.py`?**
  _High betweenness centrality (0.203) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `OptimizerEngine` (e.g. with `LLMOrchestrator` and `.__init__()`) actually correct?**
  _`OptimizerEngine` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `LocalPipelineRunner` be split into smaller, more focused modules?**
  _Cohesion score 0.12183908045977011 - nodes in this community are weakly interconnected._
- **Why does `OptimizerEngine` connect `OptimizerEngine` to `SurvivalEvaluator`, `RivenOCRAnalyzer`, `optimizer_engine.py`, `LLMOrchestrator`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `LLMOrchestrator` (e.g. with `OptimizerHTTPHandler` and `OptimizerEngine`) actually correct?**
  _`LLMOrchestrator` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `app_server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0960591133004926 - nodes in this community are weakly interconnected._
- **Why does `LLMOrchestrator` connect `LLMOrchestrator` to `app_server.py`, `OptimizerEngine`, `optimizer_engine.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
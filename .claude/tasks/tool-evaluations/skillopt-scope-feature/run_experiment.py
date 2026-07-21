#!/usr/bin/env python3
"""Validate and run the bounded SkillOpt `/scope-feature` experiment."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "local"
SKILLOPT = LOCAL / "SkillOpt"
SKILLOPT_COMMIT = "b860a5cf88ce75e2bd02ca981ac21fb28cffba83"
RUN_ROOT = LOCAL / "skillopt-scope-feature"
OUTPUT = RUN_ROOT / "run"
SEED = RUN_ROOT / "seed-skill.md"
RESULT = HERE / "results.json"
CONFIG = HERE / "config.yaml"
CODEX_WRAPPER = HERE / "codex_isolated.py"
PRODUCTION_SKILL = REPO / ".claude" / "skills" / "scope-feature" / "SKILL.md"
MODEL_CALL_MARKER = "SKILLOPT_RUN_BUDGET_ACCEPTED"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def load_results() -> dict:
    if RESULT.exists():
        return json.loads(RESULT.read_text(encoding="utf-8"))
    return {"schema_version": 1, "experiment": "X3-skillopt-scope-feature"}


def save_results(payload: dict) -> None:
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def corpus_manifest() -> dict:
    manifest = {}
    ids = set()
    for split in ("train", "val", "test"):
        path = HERE / "corpus" / split / "items.json"
        items = json.loads(path.read_text(encoding="utf-8"))
        split_ids = [str(item["id"]) for item in items]
        overlap = ids & set(split_ids)
        if overlap:
            raise RuntimeError(f"duplicate corpus ids across splits: {sorted(overlap)}")
        ids.update(split_ids)
        manifest[split] = {"count": len(items), "ids": split_ids, "sha256": sha256(path)}
    if [manifest[name]["count"] for name in ("train", "val", "test")] != [6, 2, 2]:
        raise RuntimeError(f"expected frozen 6/2/2 corpus, got {manifest}")
    return manifest


def validate() -> int:
    if not SKILLOPT.is_dir():
        raise RuntimeError("local SkillOpt checkout is missing; follow the plan's setup command")
    commit = git_output("rev-parse", "HEAD", cwd=SKILLOPT)
    if commit != SKILLOPT_COMMIT:
        raise RuntimeError(f"SkillOpt checkout drift: expected {SKILLOPT_COMMIT}, got {commit}")
    if git_output("status", "--short", cwd=SKILLOPT):
        raise RuntimeError("SkillOpt checkout has local modifications")
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if config["model"]["optimizer_backend"] != "codex_exec":
        raise RuntimeError("pilot must use the pinned Codex optimizer backend")
    if config["train"] != {
        "num_epochs": 1,
        "train_size": 6,
        "batch_size": 6,
        "accumulation": 1,
        "seed": 20260720,
    }:
        raise RuntimeError("training budget drifted from the frozen one-step contract")

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRODUCTION_SKILL, SEED)
    payload = load_results()
    completed_baseline = "baseline" in payload
    payload.update({
        "status": payload.get("status") if completed_baseline else "ready_for_budgeted_baseline",
        "base_revision": git_output("rev-parse", "HEAD"),
        "skillopt": {"package_version": "0.2.0", "source_commit": commit},
        "target": {
            "model": config["model"]["target"],
            "backend": config["model"]["target_backend"],
            "reasoning_effort": config["model"]["codex_exec_reasoning_effort"],
        },
        "optimizer": {
            "model": config["model"]["optimizer"],
            "backend": config["model"]["optimizer_backend"],
            "epochs": 1,
            "edit_budget": config["optimizer"]["learning_rate"],
        },
        "corpus": corpus_manifest(),
        "production_skill_sha256": sha256(PRODUCTION_SKILL),
        "seed_skill_sha256": sha256(SEED),
        "protected_production_surface": True,
        "model_calls_started": bool(payload.get("model_calls_started", False)),
    })
    if not completed_baseline:
        payload["next_action"] = (
            f"Set {MODEL_CALL_MARKER}=1 and run `baseline`; this makes four target calls "
            "on the untouched test split before optimization."
        )
    save_results(payload)
    print(json.dumps({
        "result": str(RESULT.relative_to(REPO)),
        "status": payload["status"],
        "corpus": {key: value["count"] for key, value in payload["corpus"].items()},
        "skillopt_commit": commit,
        "seed_matches_production": payload["production_skill_sha256"] == payload["seed_skill_sha256"],
        "next_action": payload["next_action"],
    }, indent=2))
    return 0


def require_budget() -> None:
    import os

    if os.environ.get(MODEL_CALL_MARKER) != "1":
        raise RuntimeError(
            f"model-call gate closed; set {MODEL_CALL_MARKER}=1 only for the frozen bounded phase"
        )


def configure_models(config: dict) -> None:
    from skillopt.model import (
        configure_codex_exec,
        set_optimizer_backend,
        set_optimizer_deployment,
        set_reasoning_effort,
        set_target_backend,
        set_target_deployment,
    )

    model = config["model"]
    set_optimizer_backend(model["optimizer_backend"])
    set_target_backend(model["target_backend"])
    set_optimizer_deployment(model["optimizer"])
    set_target_deployment(model["target"])
    set_reasoning_effort(model["reasoning_effort"])
    wrapper = Path(model["codex_exec_path"])
    if not wrapper.is_absolute():
        wrapper = REPO / wrapper
    configure_codex_exec(
        path=str(wrapper),
        sandbox=model["codex_exec_sandbox"],
        full_auto=model["codex_exec_full_auto"],
        reasoning_effort=model["codex_exec_reasoning_effort"],
        use_sdk=model["codex_exec_use_sdk"],
        network_access=model["codex_exec_network_access"],
        web_search=model["codex_exec_web_search"],
        approval_policy=model["codex_exec_approval_policy"],
    )


def load_adapter(config: dict):
    from adapter import ScopeFeatureAdapter

    env = config["env"]
    adapter = ScopeFeatureAdapter(
        split_dir=str(REPO / env["split_dir"]),
        split_mode=env["split_mode"],
        seed=config["train"]["seed"],
        workers=env["workers"],
        exec_timeout=env["exec_timeout"],
        max_completion_tokens=env["max_completion_tokens"],
        target_model=config["model"]["target"],
    )
    flat = {
        "split_dir": str(REPO / env["split_dir"]),
        "split_mode": env["split_mode"],
        "out_root": str(OUTPUT),
        "env": env["name"],
    }
    adapter.setup(flat)
    return adapter


def summarize_rollouts(rows: list[dict]) -> dict:
    reported_tokens = 0
    for row in rows:
        raw = str(row.get("usage", {}).get("reported_tokens", "0")).replace(",", "")
        reported_tokens += int(raw) if raw.isdigit() else 0
    return {
        "count": len(rows),
        "hard_passes": sum(int(row["hard"]) for row in rows),
        "hard_rate": sum(float(row["hard"]) for row in rows) / len(rows),
        "soft_mean": sum(float(row["soft"]) for row in rows) / len(rows),
        "reported_tokens": reported_tokens,
        "items": [
            {
                "id": row["id"],
                "hard": row["hard"],
                "soft": row["soft"],
                "fail_reason": row["fail_reason"],
            }
            for row in rows
        ],
    }


def baseline() -> int:
    require_budget()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    configure_models(config)
    adapter = load_adapter(config)
    test_items = list(adapter.dataloader.test_items)
    payload = load_results()
    if "baseline" in payload:
        raise RuntimeError(
            f"baseline evidence already exists with status {payload.get('status')!r}; do not rerun"
        )
    payload["model_calls_started"] = True
    payload["status"] = "baseline_in_progress"
    save_results(payload)
    started = time.perf_counter()
    summaries = {}
    for name, skill in (("no_skill", ""), ("current_skill", SEED.read_text(encoding="utf-8"))):
        out_dir = RUN_ROOT / "baselines" / name
        rows = adapter.rollout(test_items, skill, str(out_dir))
        summaries[name] = summarize_rollouts(rows)
    payload = load_results()
    payload["baseline"] = {
        "split": "test",
        "conditions": summaries,
        "wall_seconds": round(time.perf_counter() - started, 3),
        "raw_root": str((RUN_ROOT / "baselines").relative_to(REPO)),
    }
    no_headroom = all(
        summaries[name]["hard_rate"] == 1.0 and summaries[name]["soft_mean"] == 1.0
        for name in ("no_skill", "current_skill")
    )
    if no_headroom:
        payload["status"] = "baseline_no_discriminating_power"
        payload["disposition"] = "inconclusive_stop_before_optimization"
        payload["next_action"] = (
            "Redesign the corpus and benchmark prompt so no-skill and current-skill differ; "
            "freeze a new corpus revision before making any optimizer calls."
        )
    else:
        payload["status"] = "baseline_complete"
        payload["next_action"] = (
            f"Review baseline, then set {MODEL_CALL_MARKER}=1 and run `optimize` once. "
            "Do not rerun into the same output after a completed summary."
        )
    save_results(payload)
    print(json.dumps(payload["baseline"], indent=2))
    return 0


def load_train_module():
    path = SKILLOPT / "scripts" / "train.py"
    spec = importlib.util.spec_from_file_location("skillopt_pilot_train", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load SkillOpt train entry point: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def optimize() -> int:
    require_budget()
    payload = load_results()
    if payload.get("status") != "baseline_complete":
        raise RuntimeError("optimization requires a completed frozen baseline")
    if (OUTPUT / "summary.json").exists():
        raise RuntimeError("optimization summary already exists; do not duplicate the bounded run")
    from adapter import ScopeFeatureAdapter

    train_module = load_train_module()
    train_module._ENV_REGISTRY["scope_feature_pilot"] = ScopeFeatureAdapter
    original_argv = sys.argv
    sys.argv = [
        str(SKILLOPT / "scripts" / "train.py"),
        "--config",
        str(CONFIG),
        "--codex_exec_path",
        str(CODEX_WRAPPER),
    ]
    payload["status"] = "optimization_in_progress"
    payload["optimization_started_at_unix"] = time.time()
    save_results(payload)
    try:
        train_module.main()
    finally:
        sys.argv = original_argv
    summary_path = OUTPUT / "summary.json"
    if not summary_path.exists():
        raise RuntimeError("SkillOpt completed without summary.json")
    payload = load_results()
    payload["optimization"] = {
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        "summary_path": str(summary_path.relative_to(REPO)),
        "best_skill_path": str((OUTPUT / "best_skill.md").relative_to(REPO)),
    }
    payload["status"] = "optimization_complete_candidate_unevaluated"
    payload["next_action"] = (
        f"Set {MODEL_CALL_MARKER}=1 and run `candidate` once on the untouched test IDs, "
        "then perform human semantic review before adoption."
    )
    save_results(payload)
    return 0


def candidate() -> int:
    require_budget()
    payload = load_results()
    if payload.get("status") != "optimization_complete_candidate_unevaluated":
        raise RuntimeError("candidate evaluation requires one completed optimization run")
    best = OUTPUT / "best_skill.md"
    if not best.exists():
        raise RuntimeError("best_skill.md is missing")
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    configure_models(config)
    adapter = load_adapter(config)
    rows = adapter.rollout(
        list(adapter.dataloader.test_items),
        best.read_text(encoding="utf-8"),
        str(RUN_ROOT / "candidate-test"),
    )
    payload["candidate_test"] = summarize_rollouts(rows)
    payload["candidate_test"]["skill_sha256"] = sha256(best)
    payload["candidate_test"]["raw_root"] = str((RUN_ROOT / "candidate-test").relative_to(REPO))
    payload["status"] = "candidate_evaluated_pending_human_review"
    payload["next_action"] = (
        "Compare current_skill and candidate on every hard gate, inspect the diff for benchmark-shaped "
        "wording/context growth, then record adopt/reject/inconclusive."
    )
    save_results(payload)
    print(json.dumps(payload["candidate_test"], indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validate", "baseline", "optimize", "candidate"))
    args = parser.parse_args()
    if args.phase == "validate":
        return validate()
    if args.phase == "baseline":
        return baseline()
    if args.phase == "optimize":
        return optimize()
    return candidate()


if __name__ == "__main__":
    raise SystemExit(main())

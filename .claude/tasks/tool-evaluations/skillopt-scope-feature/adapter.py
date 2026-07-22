"""SkillOpt environment for deterministic `/scope-feature` contract scoring."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from skillopt.datasets.base import BatchSpec, SplitDataLoader
from skillopt.envs.base import EnvAdapter
from skillopt.model.codex_harness import run_target_exec


RESULT_PATTERN = re.compile(r"<scope_result>\s*(\{.*?\})\s*</scope_result>", re.DOTALL)


def write_json(path: Path, payload) -> None:
    """Persist a completed checkpoint without leaving a half-written JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _flatten(value) -> str:
    if isinstance(value, str):
        return value.lower()
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def parse_response(response: str) -> tuple[dict | None, str]:
    match = RESULT_PATTERN.search(response)
    candidate = match.group(1) if match else response.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        return None, f"invalid scope_result JSON: {error}"
    if not isinstance(payload, dict):
        return None, "scope_result must be a JSON object"
    return payload, ""


def score_response(response: str, expected: dict) -> dict:
    payload, parse_error = parse_response(response)
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("parseable_result", payload is not None, parse_error or "parsed")
    if payload is None:
        return {
            "hard": 0,
            "soft": 0.0,
            "checks": checks,
            "fail_reason": parse_error,
            "parsed": None,
        }

    outcome = str(payload.get("outcome", "")).strip().lower()
    allowed = [str(value).lower() for value in expected.get("outcomes", [])]
    check("outcome", outcome in allowed, f"got {outcome!r}; expected one of {allowed}")

    for field, minimum in expected.get("minimum_counts", {}).items():
        value = payload.get(field, [])
        actual = len(value) if isinstance(value, list) else 0
        check(f"minimum:{field}", actual >= int(minimum), f"got {actual}; minimum {minimum}")

    for field, terms in expected.get("required_terms", {}).items():
        haystack = _flatten(payload.get(field, ""))
        for term in terms:
            check(
                f"required:{field}:{term}",
                str(term).lower() in haystack,
                f"{term!r} {'present' if str(term).lower() in haystack else 'missing'}",
            )

    full_text = _flatten(payload)
    for term in expected.get("forbidden_terms", []):
        check(
            f"forbidden:{term}",
            str(term).lower() not in full_text,
            f"{term!r} {'absent' if str(term).lower() not in full_text else 'present'}",
        )

    if expected.get("assumptions_must_be_empty", False):
        assumptions = payload.get("invented_assumptions", [])
        check(
            "no_invented_assumptions",
            isinstance(assumptions, list) and not assumptions,
            f"invented_assumptions={assumptions!r}",
        )

    passed = sum(1 for row in checks if row["passed"])
    failed = [row for row in checks if not row["passed"]]
    return {
        "hard": int(not failed),
        "soft": passed / len(checks) if checks else 0.0,
        "checks": checks,
        "fail_reason": "; ".join(f"{row['name']}: {row['detail']}" for row in failed),
        "parsed": payload,
    }


def build_prompts(item: dict, skill_content: str) -> tuple[str, str]:
    guidance = skill_content.strip() or "No additional scope-feature guidance is available."
    system = (
        "You are evaluating how an engineering agent scopes work. Apply the supplied skill guidance "
        "to the case, but do not edit files, call tools, or invent missing user answers. The XML/JSON "
        "response envelope is imposed by this benchmark and must not be added to the production skill.\n\n"
        f"<skill_guidance>\n{guidance}\n</skill_guidance>"
    )
    user = (
        f"<case>\n{item['task']}\n</case>\n\n"
        "Return exactly one `<scope_result>{...}</scope_result>` object with these keys:\n"
        "- outcome: scoped | downgrade_feature | proceed_directly | needs_clarification | decision_conflict\n"
        "- rationale: concise string\n"
        "- problem: string or empty string\n"
        "- in_scope, out_of_scope, non_goals, success_criteria, unknowns, questions, "
        "refused_expansions, invented_assumptions: arrays of concise strings\n"
        "Use only facts in the case. For missing information, ask rather than infer. Preserve the "
        "owner's stated priorities and keep attractive but low-value reviewer suggestions deferred."
    )
    return system, user


class ScopeFeatureDataLoader(SplitDataLoader):
    """Use SkillOpt's deterministic committed split loader unchanged."""


class ScopeFeatureAdapter(EnvAdapter):
    def __init__(
        self,
        split_dir: str = "",
        split_mode: str = "split_dir",
        seed: int = 20260720,
        limit: int = 0,
        workers: int = 1,
        exec_timeout: int = 180,
        max_completion_tokens: int = 5000,
        target_model: str = "gpt-5.6-terra",
        **_kwargs,
    ) -> None:
        self.workers = int(workers)
        self.exec_timeout = int(exec_timeout)
        self.max_completion_tokens = int(max_completion_tokens)
        self.target_model = str(target_model)
        self.dataloader = ScopeFeatureDataLoader(
            split_dir=split_dir,
            split_mode=split_mode,
            seed=seed,
            limit=limit,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **_kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        batch = self.dataloader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs)
        return self.build_env_from_batch(batch)

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        batch = self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs)
        return self.build_env_from_batch(batch)

    def build_reference_text(self, item: dict) -> str:
        return json.dumps(item.get("expected", {}), ensure_ascii=False, sort_keys=True)

    def get_task_types(self) -> list[str]:
        return sorted({
            str(item.get("task_type", "scope"))
            for item in self.dataloader.train_items
            + self.dataloader.val_items
            + self.dataloader.test_items
        })

    def rollout(self, env_manager, skill_content: str, out_dir: str, **_kwargs) -> list[dict]:
        results = []
        for item in list(env_manager):
            item_id = str(item["id"])
            prediction_dir = Path(out_dir) / "predictions" / item_id
            checkpoint = prediction_dir / "result.json"
            if checkpoint.exists():
                results.append(json.loads(checkpoint.read_text(encoding="utf-8")))
                continue
            system, user = build_prompts(item, skill_content)
            prompt = (
                f"{system}\n\n{user}\n\n"
                "Do not inspect or modify the workspace. Respond only with the requested envelope."
            )
            exec_key = hashlib.sha256(str(prediction_dir).encode("utf-8")).hexdigest()[:16]
            exec_dir = Path(tempfile.gettempdir()) / "engineering-skills-skillopt" / exec_key
            exec_dir.mkdir(parents=True, exist_ok=True)
            response, raw = run_target_exec(
                work_dir=str(exec_dir),
                prompt=prompt,
                model=self.target_model,
                timeout=self.exec_timeout,
                sandbox="read-only",
                full_auto=False,
            )
            token_match = re.search(r"^tokens used\s*\n\s*([^\n]+)", raw, re.MULTILINE)
            usage = {
                "backend": "codex_exec",
                "reported_tokens": token_match.group(1).strip() if token_match else "unavailable",
                "raw_trace_bytes": len(raw.encode("utf-8")),
            }
            write_json(
                prediction_dir / "codex-exec.json",
                {"response": response, "raw": raw, "external_work_dir": str(exec_dir)},
            )
            scored = score_response(response, item["expected"])
            conversation = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": response},
                {
                    "role": "system",
                    "content": "[EVALUATION RESULT]\n" + json.dumps(scored, ensure_ascii=False),
                },
            ]
            result = {
                "id": item_id,
                "hard": scored["hard"],
                "soft": scored["soft"],
                "fail_reason": scored["fail_reason"],
                "predicted_answer": response,
                "response": response,
                "task_description": item["task"],
                "question": item["task"],
                "reference_text": self.build_reference_text(item),
                "task_type": item.get("task_type", "scope"),
                "target_system_prompt": system,
                "target_user_prompt": user,
                "n_turns": 1,
                "agent_ok": True,
                "usage": usage,
                "score_checks": scored["checks"],
            }
            write_json(prediction_dir / "conversation.json", conversation)
            write_json(checkpoint, result)
            results.append(result)
        write_json(Path(out_dir) / "rollouts.json", results)
        return results

"""Domain Hunter REVENANT — Agentic Sprint OS v3.0 Integration.

Implements the full Agentic Sprint OS execution protocol as an optional
--sprint mode for the main.py pipeline. Provides:
  - Sprint state management (load/save sprint-{N}-state.json)
  - Leverage gate scoring (4 axes, kill if <12/20)
  - Budget protocol (max_steps, max_tool_calls, timeout_minutes)
  - Failure protocol (3 retries with exponential backoff)
  - Artifact registry protocol (append to artifact-registry.json)
  - Step verification (run verify commands, check exit codes)
  - Decision logging in state.decisions[]

Usage:
  python -m main --sprint "Objective: deploy new SCOUT source"
  python -m main --sprint continue --state-file sprint-3-state.json

NASA Power of 10 compliant: <60 line functions, 2+ assertions per function,
fixed loop bounds, no global mutable state, immutable data at boundaries.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants (immutable, no global mutable state)
# ---------------------------------------------------------------------------
_INFRA_REGISTRY_PATH: str = "/Users/mike/Documents/good stuff/agentic/infra-registry.json"
_ARTIFACT_REGISTRY_PATH: str = "/Users/mike/Documents/good stuff/agentic/artifact-registry.json"
_SPRINT_DIR: str = "/Users/mike/Documents/good stuff/agentic"
_MAX_RETRIES: int = 3
_MAX_STEPS_HARD_LIMIT: int = 50
_MAX_TOOL_CALLS_HARD_LIMIT: int = 200
_MAX_TIMEOUT_HARD_LIMIT: int = 120
_LEVERAGE_GATE_THRESHOLD: int = 12
_LEVERAGE_GATE_MAX: int = 20


# ---------------------------------------------------------------------------
# Data structures (immutable at boundaries)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LeverageScore:
    """Immutable leverage gate scoring result."""

    scalability: int
    compounding: int
    autonomy: int
    revenue_path: int
    evidence: dict[str, str]

    @property
    def total(self) -> int:
        """Sum of all four axes (range 4-20)."""
        assert all(1 <= s <= 5 for s in (
            self.scalability, self.compounding, self.autonomy, self.revenue_path,
        )), "each axis must be 1-5"
        result = self.scalability + self.compounding + self.autonomy + self.revenue_path
        assert 4 <= result <= 20, "total must be 4-20"
        return result


@dataclass(frozen=True)
class StepDefinition:
    """Immutable definition of a single sprint step."""

    number: int
    name: str
    action: str
    tool: str
    input_ref: str
    output_ref: str
    verify_command: str
    on_fail: str
    depends_on: tuple[int, ...] = ()


@dataclass(frozen=True)
class Budget:
    """Immutable budget configuration."""

    max_steps: int
    max_tool_calls: int
    timeout_minutes: int


@dataclass
class SprintState:
    """Mutable sprint execution state (only mutated via controlled methods)."""

    sprint: str
    status: str
    current_step: int
    steps_completed: list[int]
    steps_failed: list[int]
    steps_skipped: list[int]
    artifacts: list[dict[str, str]]
    variables: dict[str, Any]
    decisions: list[dict[str, Any]]
    blocked_reason: str | None
    budget: dict[str, int]
    started_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------
def load_sprint_state(state_path: str) -> SprintState:
    """Load sprint state from JSON file on disk.

    Args:
        state_path: Absolute path to the state JSON file.

    Returns:
        Populated SprintState instance.

    Raises:
        FileNotFoundError: If state file does not exist.
        json.JSONDecodeError: If state file is invalid JSON.
    """
    assert isinstance(state_path, str) and len(state_path) > 0, "state_path required"
    assert state_path.endswith(".json"), "state file must be .json"

    with open(state_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert isinstance(data, dict), "state file must contain JSON object"
    assert "sprint" in data and "status" in data, "state file missing required fields"

    return SprintState(
        sprint=data["sprint"],
        status=data["status"],
        current_step=data.get("current_step", 1),
        steps_completed=data.get("steps_completed", []),
        steps_failed=data.get("steps_failed", []),
        steps_skipped=data.get("steps_skipped", []),
        artifacts=data.get("artifacts", []),
        variables=data.get("variables", {}),
        decisions=data.get("decisions", []),
        blocked_reason=data.get("blocked_reason"),
        budget=data.get("budget", {
            "max_steps": 20,
            "max_tool_calls": 40,
            "timeout_minutes": 30,
            "tool_calls_used": 0,
        }),
        started_at=data.get("started_at", _now_iso()),
        updated_at=data.get("updated_at", _now_iso()),
    )


def save_sprint_state(state: SprintState, state_path: str) -> None:
    """Persist sprint state to JSON file.

    Args:
        state: Current sprint state.
        state_path: Absolute path to write.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(state_path, str) and state_path.endswith(".json"), "invalid path"

    state.updated_at = _now_iso()
    data = {
        "sprint": state.sprint,
        "status": state.status,
        "current_step": state.current_step,
        "steps_completed": state.steps_completed,
        "steps_failed": state.steps_failed,
        "steps_skipped": state.steps_skipped,
        "artifacts": state.artifacts,
        "variables": state.variables,
        "decisions": state.decisions,
        "blocked_reason": state.blocked_reason,
        "budget": state.budget,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
    }
    parent = Path(state_path).parent
    parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Infrastructure registry
# ---------------------------------------------------------------------------
def load_infra_registry() -> dict[str, Any]:
    """Load the infrastructure registry from the canonical location.

    Returns:
        Parsed infra-registry.json contents as dict.

    Raises:
        FileNotFoundError: If registry does not exist.
    """
    assert os.path.isfile(_INFRA_REGISTRY_PATH), (
        f"infra-registry.json not found at {_INFRA_REGISTRY_PATH}"
    )
    assert _INFRA_REGISTRY_PATH.endswith(".json"), "must be JSON file"

    with open(_INFRA_REGISTRY_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    return data


# ---------------------------------------------------------------------------
# Leverage Gate
# ---------------------------------------------------------------------------
def score_leverage_gate(
    scalability: int,
    compounding: int,
    autonomy: int,
    revenue_path: int,
    evidence: dict[str, str],
) -> LeverageScore:
    """Create and validate a leverage gate score.

    Each axis is 1-5. Total must be >= 12/20 to proceed.

    Args:
        scalability: Score 1-5.
        compounding: Score 1-5.
        autonomy: Score 1-5.
        revenue_path: Score 1-5.
        evidence: Dict with keys matching axes, values are reasoning strings.

    Returns:
        Frozen LeverageScore instance.
    """
    assert all(1 <= s <= 5 for s in (scalability, compounding, autonomy, revenue_path)), (
        "all scores must be 1-5"
    )
    assert isinstance(evidence, dict) and len(evidence) >= 4, (
        "evidence must have entries for all 4 axes"
    )

    return LeverageScore(
        scalability=scalability,
        compounding=compounding,
        autonomy=autonomy,
        revenue_path=revenue_path,
        evidence=evidence,
    )


def enforce_leverage_gate(score: LeverageScore, state: SprintState, state_path: str) -> bool:
    """Enforce leverage gate: kill sprint if score < 12/20.

    Args:
        score: The leverage score to evaluate.
        state: Current sprint state (mutated to killed if fails).
        state_path: Path to persist state.

    Returns:
        True if gate passes, False if killed.
    """
    assert isinstance(score, LeverageScore), "score must be LeverageScore"
    assert isinstance(state, SprintState), "state must be SprintState"

    if score.total >= _LEVERAGE_GATE_THRESHOLD:
        state.decisions.append({
            "step": 0,
            "decision": f"Leverage gate PASSED ({score.total}/{_LEVERAGE_GATE_MAX})",
            "reason": json.dumps(score.evidence),
            "reversible": False,
        })
        save_sprint_state(state, state_path)
        return True

    state.status = "killed"
    state.blocked_reason = (
        f"Leverage score {score.total}/{_LEVERAGE_GATE_MAX} < {_LEVERAGE_GATE_THRESHOLD}. "
        f"Re-scope to proceed."
    )
    state.decisions.append({
        "step": 0,
        "decision": f"Leverage gate KILLED ({score.total}/{_LEVERAGE_GATE_MAX})",
        "reason": json.dumps(score.evidence),
        "reversible": False,
    })
    save_sprint_state(state, state_path)
    logger.warning(
        "sprint_killed_leverage",
        sprint=state.sprint,
        score=score.total,
        threshold=_LEVERAGE_GATE_THRESHOLD,
    )
    return False


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------
def check_budget(state: SprintState, start_time: float) -> str | None:
    """Check whether any budget limit has been exceeded.

    Args:
        state: Current sprint state.
        start_time: Monotonic time when sprint started.

    Returns:
        None if within budget, or a string describing which limit was hit.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert start_time > 0, "start_time must be positive"

    budget = state.budget
    tool_calls_used = budget.get("tool_calls_used", 0)
    max_tool_calls = budget.get("max_tool_calls", 40)
    max_steps = budget.get("max_steps", 20)
    timeout_minutes = budget.get("timeout_minutes", 30)

    if tool_calls_used >= max_tool_calls:
        return f"tool_calls ({tool_calls_used}/{max_tool_calls})"

    elapsed_minutes = (time.monotonic() - start_time) / 60.0
    if elapsed_minutes >= timeout_minutes:
        return f"timeout ({elapsed_minutes:.1f}/{timeout_minutes} min)"

    if state.current_step > max_steps:
        return f"steps ({state.current_step}/{max_steps})"

    return None


def handle_budget_exceeded(
    state: SprintState,
    state_path: str,
    reason: str,
) -> None:
    """Handle budget exceeded: persist state and prepare for halt.

    Args:
        state: Current sprint state.
        state_path: Path to persist state file.
        reason: Which budget limit was hit.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(reason, str) and len(reason) > 0, "reason required"

    state.status = "budget_exceeded"
    state.blocked_reason = f"Budget exceeded: {reason}. Resume with 'continue' or re-scope."
    state.decisions.append({
        "step": state.current_step,
        "decision": f"Budget halt: {reason}",
        "reason": "Hard limit reached per Sprint OS v3.0 budget protocol",
        "reversible": True,
    })
    save_sprint_state(state, state_path)
    logger.warning("budget_exceeded", sprint=state.sprint, reason=reason)


# ---------------------------------------------------------------------------
# Step verification
# ---------------------------------------------------------------------------
def run_verify_command(command: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Run a shell verification command and return (success, output).

    Args:
        command: Shell command to execute.
        timeout_seconds: Max seconds to wait.

    Returns:
        Tuple of (exit_code == 0, combined stdout+stderr).
    """
    assert isinstance(command, str) and len(command.strip()) > 0, "command required"
    assert 0 < timeout_seconds <= 300, "timeout must be 1-300 seconds"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd="/Users/mike/Desktop/domainhunter",
        )
        output = (result.stdout + result.stderr).strip()
        return (result.returncode == 0, output)
    except subprocess.TimeoutExpired:
        return (False, f"TIMEOUT after {timeout_seconds}s")
    except Exception as exc:
        return (False, f"EXCEPTION: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Failure protocol (3 retries, exponential backoff)
# ---------------------------------------------------------------------------
def execute_step_with_retry(
    step: StepDefinition,
    state: SprintState,
    state_path: str,
    execute_fn: Any,
) -> bool:
    """Execute a step with the failure protocol: 3 retries, exponential backoff.

    Args:
        step: The step definition to execute.
        state: Current sprint state.
        state_path: Path to persist state.
        execute_fn: Callable(step) -> bool that performs the step action.

    Returns:
        True if step succeeded (verify passed), False if exhausted retries.
    """
    assert isinstance(step, StepDefinition), "step must be StepDefinition"
    assert callable(execute_fn), "execute_fn must be callable"

    for retry_idx in range(_MAX_RETRIES):
        # Execute the step action
        action_ok = execute_fn(step)
        if not action_ok:
            _log_retry(state, step, retry_idx, "action execution failed")
            time.sleep(2 ** retry_idx)
            continue

        # Increment tool call budget
        state.budget["tool_calls_used"] = state.budget.get("tool_calls_used", 0) + 1
        save_sprint_state(state, state_path)

        # Verify
        if not step.verify_command or step.verify_command == "none":
            return True

        passed, output = run_verify_command(step.verify_command)
        if passed:
            logger.info(
                "step_verified",
                step=step.number,
                name=step.name,
                output=output[:200],
            )
            return True

        _log_retry(state, step, retry_idx, f"verify failed: {output[:200]}")
        time.sleep(2 ** retry_idx)

    return False


def _log_retry(state: SprintState, step: StepDefinition, retry_idx: int, reason: str) -> None:
    """Log a retry attempt to state decisions.

    Args:
        state: Sprint state.
        step: Step being retried.
        retry_idx: Current retry index (0-based).
        reason: Why the retry is happening.
    """
    assert 0 <= retry_idx < _MAX_RETRIES, "retry_idx out of bounds"
    assert isinstance(reason, str), "reason must be string"

    state.decisions.append({
        "step": step.number,
        "decision": f"Retry {retry_idx + 1}/{_MAX_RETRIES} for step {step.number}",
        "reason": reason,
        "reversible": True,
    })


def handle_step_failure(
    step: StepDefinition,
    remaining_steps: list[StepDefinition],
    state: SprintState,
    state_path: str,
) -> bool:
    """Handle a step that exhausted all retries.

    Checks if remaining steps depend on this step. If no dependency, skip.
    If dependency exists, block the sprint.

    Args:
        step: The failed step.
        remaining_steps: Steps not yet executed.
        state: Sprint state.
        state_path: Path to persist state.

    Returns:
        True if sprint can continue (step skipped), False if blocked.
    """
    assert isinstance(step, StepDefinition), "step must be StepDefinition"
    assert isinstance(remaining_steps, list), "remaining_steps must be list"

    state.steps_failed.append(step.number)

    # Check if any remaining step depends on this one
    has_dependency = False
    for future_step in remaining_steps:
        if step.number in future_step.depends_on:
            has_dependency = True
            break

    if not has_dependency:
        state.steps_skipped.append(step.number)
        state.decisions.append({
            "step": step.number,
            "decision": f"Skip step {step.number} (no downstream dependency)",
            "reason": f"Step '{step.name}' failed after {_MAX_RETRIES} retries, no blockers",
            "reversible": True,
        })
        save_sprint_state(state, state_path)
        logger.warning("step_skipped", step=step.number, name=step.name)
        return True

    state.status = "blocked"
    state.blocked_reason = (
        f"Step {step.number} ('{step.name}') failed after {_MAX_RETRIES} retries "
        f"and has downstream dependencies."
    )
    state.decisions.append({
        "step": step.number,
        "decision": f"Sprint BLOCKED at step {step.number}",
        "reason": state.blocked_reason,
        "reversible": False,
    })
    save_sprint_state(state, state_path)
    logger.error("sprint_blocked", step=step.number, name=step.name)
    return False


# ---------------------------------------------------------------------------
# Artifact registry
# ---------------------------------------------------------------------------
def append_to_artifact_registry(
    sprint_slug: str,
    artifacts: list[dict[str, str]],
) -> None:
    """Append sprint artifacts to the master artifact registry.

    Args:
        sprint_slug: Sprint identifier (e.g., "3-scout-upgrade").
        artifacts: List of artifact dicts with path, type, purpose, deploy_target.
    """
    assert isinstance(sprint_slug, str) and len(sprint_slug) > 0, "sprint_slug required"
    assert isinstance(artifacts, list), "artifacts must be list"

    registry_path = Path(_ARTIFACT_REGISTRY_PATH)
    if registry_path.exists():
        with open(registry_path, "r", encoding="utf-8") as fh:
            registry = json.load(fh)
    else:
        registry = {"version": "1.0", "last_updated": _now_iso(), "artifacts": []}

    assert isinstance(registry, dict), "registry must be dict"
    assert "artifacts" in registry, "registry must have artifacts key"

    new_entry = {
        "sprint": sprint_slug,
        "date": _now_iso(),
        "artifacts": artifacts,
    }
    registry["artifacts"].append(new_entry)
    registry["last_updated"] = _now_iso()

    with open(registry_path, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2)
        fh.write("\n")

    logger.info(
        "artifact_registry_updated",
        sprint=sprint_slug,
        artifact_count=len(artifacts),
    )


# ---------------------------------------------------------------------------
# Sprint initialization
# ---------------------------------------------------------------------------
def initialize_sprint_state(
    sprint_number: int,
    slug: str,
    budget: Budget,
) -> SprintState:
    """Create a fresh sprint state for a new sprint.

    Args:
        sprint_number: Sequential sprint number.
        slug: Short sprint descriptor (kebab-case).
        budget: Budget configuration.

    Returns:
        New SprintState in "in_progress" status.
    """
    assert sprint_number > 0, "sprint_number must be positive"
    assert isinstance(slug, str) and len(slug) > 0, "slug required"

    sprint_id = f"{sprint_number}-{slug}"
    return SprintState(
        sprint=sprint_id,
        status="in_progress",
        current_step=1,
        steps_completed=[],
        steps_failed=[],
        steps_skipped=[],
        artifacts=[],
        variables={},
        decisions=[],
        blocked_reason=None,
        budget={
            "max_steps": min(budget.max_steps, _MAX_STEPS_HARD_LIMIT),
            "max_tool_calls": min(budget.max_tool_calls, _MAX_TOOL_CALLS_HARD_LIMIT),
            "timeout_minutes": min(budget.timeout_minutes, _MAX_TIMEOUT_HARD_LIMIT),
            "tool_calls_used": 0,
        },
        started_at=_now_iso(),
        updated_at=_now_iso(),
    )


def get_state_file_path(sprint_id: str) -> str:
    """Compute the canonical state file path for a sprint.

    Args:
        sprint_id: Sprint identifier (e.g., "3-scout-upgrade").

    Returns:
        Absolute path to the state JSON file.
    """
    assert isinstance(sprint_id, str) and len(sprint_id) > 0, "sprint_id required"
    assert "-" in sprint_id, "sprint_id must be in format N-slug"

    return os.path.join(_SPRINT_DIR, f"sprint-{sprint_id}-state.json")


# ---------------------------------------------------------------------------
# Sprint execution engine
# ---------------------------------------------------------------------------
def _process_single_step(
    step: StepDefinition,
    step_idx: int,
    steps: list[StepDefinition],
    state: SprintState,
    state_path: str,
    execute_fn: Any,
) -> str:
    """Process one step: execute, verify, handle success/failure.

    Args:
        step: The step to execute.
        step_idx: Index of this step in the steps list.
        steps: Full list of steps (for dependency check).
        state: Sprint state.
        state_path: State file path.
        execute_fn: Step executor callable.

    Returns:
        "ok" if step succeeded, "skip" if already done, "halt" to stop sprint.
    """
    assert isinstance(step, StepDefinition), "step must be StepDefinition"
    assert 0 <= step_idx < len(steps), "step_idx out of bounds"

    # Skip already-completed or skipped steps (for resume)
    if step.number in state.steps_completed or step.number in state.steps_skipped:
        return "skip"

    state.current_step = step.number
    save_sprint_state(state, state_path)
    logger.info("step_start", step=step.number, name=step.name)

    success = execute_step_with_retry(step, state, state_path, execute_fn)

    if success:
        state.steps_completed.append(step.number)
        save_sprint_state(state, state_path)
        logger.info("step_complete", step=step.number, name=step.name)
        return "ok"

    remaining = steps[step_idx + 1:]
    can_continue = handle_step_failure(step, remaining, state, state_path)
    return "ok" if can_continue else "halt"


def execute_sprint(
    steps: list[StepDefinition],
    state: SprintState,
    state_path: str,
    execute_fn: Any,
    start_time: float,
) -> SprintState:
    """Execute all sprint steps sequentially with budget/failure protocols.

    Args:
        steps: Ordered list of step definitions.
        state: Current sprint state (mutated in place).
        state_path: Path to persist state after each step.
        execute_fn: Callable(step) -> bool that performs step actions.
        start_time: Monotonic timestamp when sprint execution began.

    Returns:
        Final sprint state after execution.
    """
    assert isinstance(steps, list) and len(steps) <= _MAX_STEPS_HARD_LIMIT, (
        f"steps must be list of max {_MAX_STEPS_HARD_LIMIT}"
    )
    assert callable(execute_fn), "execute_fn must be callable"

    for step_idx in range(len(steps)):
        budget_issue = check_budget(state, start_time)
        if budget_issue is not None:
            handle_budget_exceeded(state, state_path, budget_issue)
            return state

        result = _process_single_step(
            steps[step_idx], step_idx, steps, state, state_path, execute_fn,
        )
        if result == "halt":
            return state

    return state


def finalize_sprint(
    state: SprintState,
    state_path: str,
    success_criteria: list[str],
) -> bool:
    """Finalize a sprint: run success criteria, update registry.

    Args:
        state: Sprint state after all steps executed.
        state_path: Path to state file.
        success_criteria: List of verify commands that must all pass.

    Returns:
        True if sprint is completed successfully, False otherwise.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(success_criteria, list), "success_criteria must be list"

    # Run all success criteria verify commands
    all_passed = True
    for crit_idx, criterion in enumerate(success_criteria):
        if crit_idx >= _MAX_STEPS_HARD_LIMIT:
            break
        passed, output = run_verify_command(criterion)
        if not passed:
            all_passed = False
            state.decisions.append({
                "step": state.current_step,
                "decision": f"Success criterion {crit_idx + 1} FAILED",
                "reason": output[:300],
                "reversible": True,
            })
            logger.warning(
                "success_criterion_failed",
                index=crit_idx + 1,
                command=criterion,
                output=output[:200],
            )

    if all_passed:
        state.status = "completed"
        # Append artifacts to registry
        if state.artifacts:
            append_to_artifact_registry(state.sprint, state.artifacts)
        save_sprint_state(state, state_path)
        logger.info("sprint_completed", sprint=state.sprint)
        return True

    state.status = "criteria_failed"
    state.blocked_reason = "One or more success criteria failed verification."
    save_sprint_state(state, state_path)
    logger.error("sprint_criteria_failed", sprint=state.sprint)
    return False


# ---------------------------------------------------------------------------
# Sprint plan generation
# ---------------------------------------------------------------------------
def _render_leverage_table(leverage: LeverageScore) -> list[str]:
    """Render the leverage gate as markdown table lines.

    Args:
        leverage: Leverage score to render.

    Returns:
        List of markdown lines for the leverage gate table.
    """
    assert isinstance(leverage, LeverageScore), "leverage must be LeverageScore"
    assert leverage.total >= 4, "total must be at least 4 (all axes >= 1)"

    return [
        "## Leverage Gate",
        "| Axis | Score (1-5) | Evidence |",
        "|------|-------------|----------|",
        f"| Scalability | {leverage.scalability} | {leverage.evidence.get('scalability', '')} |",
        f"| Compounding | {leverage.compounding} | {leverage.evidence.get('compounding', '')} |",
        f"| Autonomy | {leverage.autonomy} | {leverage.evidence.get('autonomy', '')} |",
        f"| Revenue path | {leverage.revenue_path} | {leverage.evidence.get('revenue_path', '')} |",
        f"| **Total** | **{leverage.total}/20** | |",
    ]


def _render_steps_section(steps: list[StepDefinition]) -> list[str]:
    """Render all steps as markdown sections.

    Args:
        steps: Step definitions to render.

    Returns:
        List of markdown lines.
    """
    assert isinstance(steps, list), "steps must be list"
    assert len(steps) <= _MAX_STEPS_HARD_LIMIT, "too many steps"

    lines: list[str] = ["## Steps", ""]
    for step in steps:
        lines.append(f"### Step {step.number}: {step.name}")
        lines.append(f"- **Do**: {step.action}")
        lines.append(f"- **Tool**: {step.tool}")
        lines.append(f"- **Input**: {step.input_ref}")
        lines.append(f"- **Output**: {step.output_ref}")
        lines.append(f"- **Verify**: `{step.verify_command}`")
        lines.append(f"- **On fail**: {step.on_fail}")
        lines.append("")
    return lines


def generate_sprint_plan(
    sprint_number: int,
    slug: str,
    objective: str,
    steps: list[StepDefinition],
    leverage: LeverageScore,
    budget: Budget,
    infra: dict[str, Any],
) -> str:
    """Generate a filled sprint plan from the template.

    Args:
        sprint_number: Sprint sequence number.
        slug: Sprint slug (kebab-case).
        objective: One-line objective.
        steps: List of step definitions.
        leverage: Leverage gate scores.
        budget: Budget configuration.
        infra: Loaded infra registry (for reference).

    Returns:
        Filled markdown sprint plan as string.
    """
    assert sprint_number > 0, "sprint_number must be positive"
    assert isinstance(objective, str) and len(objective) > 0, "objective required"

    lines: list[str] = [
        f"# Sprint {sprint_number}: {slug}",
        "",
        "## Objective",
        objective,
        "",
    ]
    lines.extend(_render_leverage_table(leverage))
    lines.extend([
        "",
        "## Budget",
        f"- **Max steps**: {budget.max_steps}",
        f"- **Max tool calls**: {budget.max_tool_calls}",
        f"- **Timeout**: {budget.timeout_minutes} minutes",
        "",
    ])
    lines.extend(_render_steps_section(steps))

    return "\n".join(lines)


def save_sprint_plan(sprint_number: int, slug: str, plan_content: str) -> str:
    """Save a generated sprint plan to the sprint directory.

    Args:
        sprint_number: Sprint sequence number.
        slug: Sprint slug.
        plan_content: Markdown content of the plan.

    Returns:
        Absolute path to the saved plan file.
    """
    assert sprint_number > 0, "sprint_number must be positive"
    assert isinstance(plan_content, str) and len(plan_content) > 0, "plan_content required"

    filename = f"sprint-{sprint_number}-{slug}.md"
    filepath = os.path.join(_SPRINT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(plan_content)

    return filepath


# ---------------------------------------------------------------------------
# Resume protocol
# ---------------------------------------------------------------------------
def _reverify_completed_steps(
    state: SprintState,
    steps_by_number: dict[int, StepDefinition],
) -> list[int]:
    """Re-verify all previously completed steps and return those that still pass.

    Args:
        state: Sprint state with steps_completed list.
        steps_by_number: Mapping of step number to definition.

    Returns:
        List of step numbers that still verify successfully.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(steps_by_number, dict), "steps_by_number must be dict"

    reverified: list[int] = []
    for step_num in list(state.steps_completed):
        step_def = steps_by_number.get(step_num)
        if step_def is None:
            continue
        if not step_def.verify_command or step_def.verify_command == "none":
            reverified.append(step_num)
            continue

        passed, output = run_verify_command(step_def.verify_command)
        if passed:
            reverified.append(step_num)
        else:
            state.decisions.append({
                "step": step_num,
                "decision": f"Re-verify FAILED for step {step_num} on resume",
                "reason": output[:200],
                "reversible": True,
            })
            logger.warning("resume_reverify_failed", step=step_num, name=step_def.name)

    return reverified


def resume_sprint(
    state_path: str,
    steps: list[StepDefinition],
) -> SprintState:
    """Resume a sprint by re-verifying completed steps.

    Per Sprint OS protocol: re-run verify commands for all steps_completed.
    Any verification failure moves the step back to pending for re-execution.

    Args:
        state_path: Path to existing state file.
        steps: Full list of step definitions.

    Returns:
        Updated state ready for execution from first incomplete step.
    """
    assert os.path.isfile(state_path), f"state file not found: {state_path}"
    assert isinstance(steps, list) and len(steps) > 0, "steps required"

    state = load_sprint_state(state_path)
    steps_by_number = {s.number: s for s in steps}
    state.steps_completed = _reverify_completed_steps(state, steps_by_number)

    # Find first incomplete step
    for step in steps:
        if step.number not in state.steps_completed and step.number not in state.steps_skipped:
            state.current_step = step.number
            break

    state.status = "in_progress"
    state.blocked_reason = None
    state.budget["tool_calls_used"] = 0
    save_sprint_state(state, state_path)

    return state


# ---------------------------------------------------------------------------
# CLI integration (called from main.py)
# ---------------------------------------------------------------------------
def add_sprint_args(parser: Any) -> None:
    """Add --sprint mode arguments to the main argparse parser.

    Args:
        parser: argparse.ArgumentParser instance from main.py.
    """
    assert parser is not None, "parser required"
    assert hasattr(parser, "add_argument"), "parser must be ArgumentParser"

    parser.add_argument(
        "--sprint",
        type=str,
        default=None,
        metavar="OBJECTIVE",
        help=(
            "Run in Agentic Sprint OS mode. Pass an objective string "
            "or 'continue' to resume a previous sprint."
        ),
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to existing sprint state file (for resume/continue).",
    )
    parser.add_argument(
        "--sprint-number",
        type=int,
        default=None,
        metavar="N",
        help="Sprint number (auto-detected if not specified).",
    )
    parser.add_argument(
        "--sprint-slug",
        type=str,
        default=None,
        metavar="SLUG",
        help="Sprint slug in kebab-case (auto-generated from objective if not specified).",
    )


def is_sprint_mode(args: Any) -> bool:
    """Check if the parsed args indicate sprint mode.

    Args:
        args: Parsed argparse namespace.

    Returns:
        True if --sprint was provided.
    """
    assert args is not None, "args required"
    assert hasattr(args, "sprint"), "args missing sprint attribute (call add_sprint_args first)"

    return args.sprint is not None


def run_sprint_mode(args: Any) -> int:
    """Entry point for sprint mode execution.

    Called from main.py when --sprint is detected. Orchestrates the full
    sprint lifecycle: init/resume, leverage gate, execution, finalization.

    Args:
        args: Parsed argparse namespace with sprint fields.

    Returns:
        Exit code (0 = success, 1 = failure/blocked/killed, 2 = budget exceeded).
    """
    assert is_sprint_mode(args), "not in sprint mode"
    assert hasattr(args, "state_file"), "args missing state_file"

    # Load infra registry
    infra = load_infra_registry()
    logger.info("infra_loaded", apis=len(infra.get("apis", {})))

    if args.sprint.lower() == "continue":
        return _handle_continue(args, infra)
    return _handle_new_sprint(args, infra)


def _handle_continue(args: Any, infra: dict[str, Any]) -> int:
    """Handle 'continue' mode: resume a previous sprint.

    Args:
        args: Parsed args with state_file path.
        infra: Loaded infrastructure registry.

    Returns:
        Exit code.
    """
    assert args.state_file is not None, (
        "--state-file required when using --sprint continue"
    )
    assert os.path.isfile(args.state_file), f"state file not found: {args.state_file}"

    state_path = args.state_file
    logger.info("sprint_resume", state_path=state_path)

    # For resume, we need the steps. Load them from the state's variables
    state = load_sprint_state(state_path)
    steps = _reconstruct_steps_from_state(state)

    if not steps:
        logger.error("no_steps_in_state", sprint=state.sprint)
        print("ERROR: Cannot resume - no steps found in state file.", file=sys.stderr)
        return 1

    # Resume protocol
    state = resume_sprint(state_path, steps)
    start_time = time.monotonic()

    # Execute remaining steps
    state = execute_sprint(
        steps, state, state_path, _default_execute_fn, start_time,
    )

    return _resolve_final_status(state)


def _handle_new_sprint(args: Any, infra: dict[str, Any]) -> int:
    """Handle a new sprint with a fresh objective.

    Args:
        args: Parsed args with sprint objective.
        infra: Loaded infrastructure registry.

    Returns:
        Exit code.
    """
    assert isinstance(args.sprint, str) and len(args.sprint) > 0, "objective required"
    assert isinstance(infra, dict), "infra must be dict"

    objective = args.sprint
    sprint_number = args.sprint_number or _detect_next_sprint_number()
    slug = args.sprint_slug or _slugify(objective)

    logger.info(
        "sprint_new",
        number=sprint_number,
        slug=slug,
        objective=objective,
    )

    # Initialize state with default budget
    budget = Budget(max_steps=20, max_tool_calls=40, timeout_minutes=30)
    state = initialize_sprint_state(sprint_number, slug, budget)
    state_path = get_state_file_path(state.sprint)

    # Store objective in variables for resume
    state.variables["objective"] = objective
    state.variables["infra_loaded"] = True
    save_sprint_state(state, state_path)

    print(f"Sprint {sprint_number}-{slug} initialized.")
    print(f"State file: {state_path}")
    print(f"Objective: {objective}")
    print("")
    print("Sprint is ready for step definitions.")
    print("Define steps via sprint plan or programmatic step injection,")
    print("then execute with: --sprint continue --state-file " + state_path)

    return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format.

    Returns:
        ISO 8601 formatted UTC timestamp string.
    """
    now = datetime.now(timezone.utc)
    assert now.year >= 2024, "system clock is invalid"
    result = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert len(result) == 20, "ISO timestamp must be 20 chars"
    return result


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug (max 30 chars).

    Args:
        text: Input text to slugify.

    Returns:
        Kebab-case string.
    """
    assert isinstance(text, str) and len(text) > 0, "text required"
    assert len(text) < 500, "text too long for slug"

    slug = text.lower().strip()
    # Replace non-alpha with hyphens
    result: list[str] = []
    for char_idx, char in enumerate(slug):
        if char_idx >= 30:
            break
        if char.isalnum():
            result.append(char)
        elif char in (" ", "-", "_"):
            if result and result[-1] != "-":
                result.append("-")

    return "".join(result).strip("-") or "sprint"


def _detect_next_sprint_number() -> int:
    """Detect the next sprint number by scanning existing state files.

    Returns:
        Next available sprint number (max existing + 1, minimum 1).
    """
    sprint_dir = Path(_SPRINT_DIR)
    assert isinstance(_SPRINT_DIR, str) and len(_SPRINT_DIR) > 0, "sprint dir must be set"
    max_num = 0

    if sprint_dir.exists():
        assert sprint_dir.is_dir(), f"{_SPRINT_DIR} must be a directory"
        for entry_idx, entry in enumerate(sorted(sprint_dir.iterdir())):
            if entry_idx >= 500:
                break
            if entry.name.startswith("sprint-") and entry.name.endswith("-state.json"):
                parts = entry.name.replace("sprint-", "").replace("-state.json", "")
                num_str = parts.split("-")[0] if "-" in parts else parts
                try:
                    num = int(num_str)
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue

    return max_num + 1


def _reconstruct_steps_from_state(state: SprintState) -> list[StepDefinition]:
    """Reconstruct step definitions from state variables.

    For resume, steps should be stored in state.variables["steps"].

    Args:
        state: Sprint state that may contain step data.

    Returns:
        List of StepDefinition instances, or empty list if not found.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(state.variables, dict), "state.variables must be dict"

    raw_steps = state.variables.get("steps", [])
    if not raw_steps:
        return []

    steps: list[StepDefinition] = []
    for s_idx, raw in enumerate(raw_steps):
        if s_idx >= _MAX_STEPS_HARD_LIMIT:
            break
        steps.append(StepDefinition(
            number=raw.get("number", s_idx + 1),
            name=raw.get("name", f"step-{s_idx + 1}"),
            action=raw.get("action", ""),
            tool=raw.get("tool", ""),
            input_ref=raw.get("input_ref", ""),
            output_ref=raw.get("output_ref", ""),
            verify_command=raw.get("verify_command", ""),
            on_fail=raw.get("on_fail", "retry"),
            depends_on=tuple(raw.get("depends_on", ())),
        ))

    return steps


def _default_execute_fn(step: StepDefinition) -> bool:
    """Default step executor: runs step.tool as a shell command.

    For integration with the Domain Hunter pipeline, this runs the tool
    command specified in the step definition.

    Args:
        step: Step to execute.

    Returns:
        True if command ran without error, False otherwise.
    """
    assert isinstance(step, StepDefinition), "step must be StepDefinition"
    assert isinstance(step.tool, str), "step.tool must be string"

    if not step.tool or step.tool == "none" or step.tool == "manual":
        # Steps that don't have automated tools are marked as pass-through
        return True

    passed, output = run_verify_command(step.tool, timeout_seconds=120)
    if not passed:
        logger.warning("step_execute_failed", step=step.number, output=output[:200])
    return passed


def _resolve_final_status(state: SprintState) -> int:
    """Map final sprint status to an exit code.

    Args:
        state: Final sprint state.

    Returns:
        0 for completed, 1 for blocked/killed/failed, 2 for budget_exceeded.
    """
    assert isinstance(state, SprintState), "state must be SprintState"
    assert isinstance(state.status, str), "state.status must be string"

    status_map = {
        "completed": 0,
        "in_progress": 0,
        "killed": 1,
        "blocked": 1,
        "criteria_failed": 1,
        "budget_exceeded": 2,
    }
    exit_code = status_map.get(state.status, 1)

    print(f"\nSprint {state.sprint}: {state.status}")
    print(f"  Steps completed: {len(state.steps_completed)}")
    print(f"  Steps failed: {len(state.steps_failed)}")
    print(f"  Steps skipped: {len(state.steps_skipped)}")
    print(f"  Decisions logged: {len(state.decisions)}")
    print(f"  Tool calls used: {state.budget.get('tool_calls_used', 0)}")

    if state.blocked_reason:
        print(f"  Blocked: {state.blocked_reason}")

    return exit_code


# ---------------------------------------------------------------------------
# Programmatic step injection (for pipeline integration)
# ---------------------------------------------------------------------------
def inject_steps_into_state(
    state_path: str,
    steps: list[StepDefinition],
) -> None:
    """Store step definitions into state file for later resume.

    This allows the Domain Hunter pipeline to programmatically define
    sprint steps and then execute them via the orchestrator.

    Args:
        state_path: Path to existing state file.
        steps: Steps to store.
    """
    assert os.path.isfile(state_path), f"state file not found: {state_path}"
    assert isinstance(steps, list) and len(steps) > 0, "steps required"

    state = load_sprint_state(state_path)
    state.variables["steps"] = [
        {
            "number": s.number,
            "name": s.name,
            "action": s.action,
            "tool": s.tool,
            "input_ref": s.input_ref,
            "output_ref": s.output_ref,
            "verify_command": s.verify_command,
            "on_fail": s.on_fail,
            "depends_on": list(s.depends_on),
        }
        for s in steps
    ]
    save_sprint_state(state, state_path)
    logger.info("steps_injected", count=len(steps), state_path=state_path)

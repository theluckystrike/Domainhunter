"""Agentic Sprint OS — Artifact Registry Module.

Tracks sprint artifacts with type classification, deploy targets, and history.
NASA Power of 10 compliant: bounded loops, <60 line functions, 2+ assertions,
no global mutable state, proper error handling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

# Fixed bound for loop iterations (NASA P10 Rule 2)
MAX_ARTIFACTS: int = 10_000
MAX_SPRINTS: int = 1_000

VALID_TYPES: frozenset[str] = frozenset(
    ("code", "config", "data", "content", "infra")
)


@dataclass(frozen=True)
class Artifact:
    """Immutable record of a single sprint artifact."""

    path: str
    type: str
    purpose: str
    deploy_target: str | None
    created_at: str


@dataclass(frozen=True)
class SprintArtifacts:
    """Immutable record of all artifacts produced in a single sprint."""

    sprint: str
    date: str
    artifacts: tuple[Artifact, ...]


def validate_artifact(artifact: Artifact) -> tuple[bool, str]:
    """Validate an artifact's fields. Returns (is_valid, error_message).

    Checks type membership, non-empty path/purpose, and ISO8601 date format.
    """
    assert isinstance(artifact, Artifact), "Input must be an Artifact instance"
    assert isinstance(artifact.path, str), "Artifact path must be a string"

    if not artifact.path.strip():
        return False, "path must not be empty"

    if artifact.type not in VALID_TYPES:
        return False, f"type must be one of {sorted(VALID_TYPES)}, got '{artifact.type}'"

    if not artifact.purpose.strip():
        return False, "purpose must not be empty"

    if not artifact.created_at.strip():
        return False, "created_at must not be empty"

    # Validate ISO8601 format
    try:
        datetime.fromisoformat(artifact.created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False, f"created_at is not valid ISO8601: '{artifact.created_at}'"

    return True, ""


def load_registry(path: Path) -> list[SprintArtifacts]:
    """Load the artifact registry from a JSON file.

    Returns an empty list if the file does not exist or contains no sprints.
    Raises ValueError on malformed data.
    """
    assert isinstance(path, Path), "path must be a Path object"
    assert MAX_SPRINTS > 0, "MAX_SPRINTS must be positive"

    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Failed to read registry at {path}: {exc}") from exc

    sprints_raw = raw.get("sprints", [])
    result: list[SprintArtifacts] = []

    for idx, sprint_data in enumerate(sprints_raw):
        if idx >= MAX_SPRINTS:
            break

        artifacts: list[Artifact] = []
        for art_idx, art_data in enumerate(sprint_data.get("artifacts", [])):
            if art_idx >= MAX_ARTIFACTS:
                break
            artifacts.append(Artifact(
                path=art_data["path"],
                type=art_data["type"],
                purpose=art_data["purpose"],
                deploy_target=art_data.get("deploy_target"),
                created_at=art_data["created_at"],
            ))

        result.append(SprintArtifacts(
            sprint=sprint_data["sprint"],
            date=sprint_data["date"],
            artifacts=tuple(artifacts),
        ))

    return result


def append_sprint(
    registry_path: Path, sprint_slug: str, artifacts: list[Artifact]
) -> None:
    """Append a new sprint entry to the registry JSON file.

    Creates the file if it does not exist. Validates all artifacts before writing.
    """
    assert isinstance(registry_path, Path), "registry_path must be a Path object"
    assert sprint_slug and sprint_slug.strip(), "sprint_slug must not be empty"

    # Validate every artifact before persisting
    for art in artifacts[:MAX_ARTIFACTS]:
        is_valid, err = validate_artifact(art)
        if not is_valid:
            raise ValueError(f"Invalid artifact '{art.path}': {err}")

    # Load existing data or create skeleton
    if registry_path.exists():
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Failed to read registry: {exc}") from exc
    else:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": "1.0", "sprints": []}

    # Ensure sprints key exists
    if "sprints" not in data:
        data["sprints"] = []

    now_iso = datetime.now(timezone.utc).isoformat()

    sprint_entry = {
        "sprint": sprint_slug,
        "date": now_iso,
        "artifacts": [asdict(a) for a in artifacts[:MAX_ARTIFACTS]],
    }

    data["sprints"].append(sprint_entry)
    data["last_updated"] = now_iso

    registry_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_by_deploy_target(
    registry: list[SprintArtifacts], target: str
) -> list[Artifact]:
    """Find all artifacts destined for a specific deploy target.

    Returns artifacts across all sprints matching the target string exactly.
    """
    assert isinstance(registry, list), "registry must be a list"
    assert target and target.strip(), "target must not be empty"

    results: list[Artifact] = []
    count = 0

    for sprint in registry[:MAX_SPRINTS]:
        for artifact in sprint.artifacts:
            if count >= MAX_ARTIFACTS:
                break
            if artifact.deploy_target == target:
                results.append(artifact)
            count += 1

    return results


def find_by_type(
    registry: list[SprintArtifacts], artifact_type: str
) -> list[Artifact]:
    """Find all artifacts of a specific type across all sprints.

    Valid types: code, config, data, content, infra.
    """
    assert isinstance(registry, list), "registry must be a list"
    assert artifact_type in VALID_TYPES, (
        f"artifact_type must be one of {sorted(VALID_TYPES)}, got '{artifact_type}'"
    )

    results: list[Artifact] = []
    count = 0

    for sprint in registry[:MAX_SPRINTS]:
        for artifact in sprint.artifacts:
            if count >= MAX_ARTIFACTS:
                break
            if artifact.type == artifact_type:
                results.append(artifact)
            count += 1

    return results


def get_sprint_history(registry: list[SprintArtifacts]) -> list[str]:
    """Return ordered list of sprint slugs from the registry.

    Preserves chronological order (earliest first).
    """
    assert isinstance(registry, list), "registry must be a list"
    assert len(registry) <= MAX_SPRINTS, (
        f"registry exceeds MAX_SPRINTS ({MAX_SPRINTS})"
    )

    return [sprint.sprint for sprint in registry[:MAX_SPRINTS]]

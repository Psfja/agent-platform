from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import VersionSnapshot


def get_snapshot(db: Session, project_id: str, version: str) -> VersionSnapshot:
    snapshot = db.scalar(
        select(VersionSnapshot).where(
            VersionSnapshot.project_id == project_id,
            VersionSnapshot.version == version,
        )
    )
    if not snapshot:
        raise not_found("版本", version)
    return snapshot


def compare_versions(db: Session, project_id: str, from_version: str, to_version: str) -> dict[str, Any]:
    old = get_snapshot(db, project_id, from_version)
    new = get_snapshot(db, project_id, to_version)
    old_files = old.code_manifest.get("files", {})
    new_files = new.code_manifest.get("files", {})
    paths = sorted(set(old_files) | set(new_files))
    files: list[dict[str, Any]] = []
    additions = deletions = 0
    for path in paths:
        before = old_files.get(path)
        after = new_files.get(path)
        if before == after:
            continue
        if before is None:
            change_type = "A"
            added, removed = int(after.get("lines", 1)), 0
        elif after is None:
            change_type = "D"
            added, removed = 0, int(before.get("lines", 1))
        else:
            change_type = "M"
            added = max(1, int(after.get("lines", 1)) - int(before.get("lines", 1))) + int(after.get("churn", 0))
            removed = int(after.get("removed", 0))
        additions += added
        deletions += removed
        files.append({"path": path, "type": change_type, "added": added, "removed": removed})

    old_api = old.api_snapshot.get("endpoints", {})
    new_api = new.api_snapshot.get("endpoints", {})
    api_changes = []
    for endpoint in sorted(set(old_api) | set(new_api)):
        if endpoint not in old_api:
            api_changes.append({"endpoint": endpoint, "type": "added", "breaking": False})
        elif endpoint not in new_api:
            api_changes.append({"endpoint": endpoint, "type": "removed", "breaking": True})
        elif old_api[endpoint] != new_api[endpoint]:
            breaking = old_api[endpoint].get("signature") != new_api[endpoint].get("signature")
            api_changes.append({"endpoint": endpoint, "type": "modified", "breaking": breaking})

    old_schema = old.code_manifest.get("schema", {})
    new_schema = new.code_manifest.get("schema", {})
    schema_changes = []
    for item in sorted(set(old_schema) | set(new_schema)):
        if item not in old_schema:
            schema_changes.append({"object": item, "type": "added", "breaking": False})
        elif item not in new_schema:
            schema_changes.append({"object": item, "type": "removed", "breaking": True})
        elif old_schema[item] != new_schema[item]:
            schema_changes.append({"object": item, "type": "modified", "breaking": False})

    old_features = set(old.code_manifest.get("features", []))
    new_features = set(new.code_manifest.get("features", []))
    has_breaking = any(item.get("breaking") for item in api_changes + schema_changes)
    return {
        "from_version": from_version,
        "to_version": to_version,
        "summary": {"files": len(files), "added": additions, "removed": deletions},
        "files": files,
        "schema_changes": schema_changes,
        "api_changes": api_changes,
        "feature_changes": {
            "added": sorted(new_features - old_features),
            "removed": sorted(old_features - new_features),
            "unchanged": sorted(old_features & new_features),
        },
        "has_breaking_changes": has_breaking,
    }

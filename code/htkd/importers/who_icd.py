 # py code beginning 
 
 # py code beginning

"""WHO ICD-11 Foundation + MMS importer for HTKD."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from typing import Any

import requests
from sqlalchemy import Engine, text

from htkd.db.htkd_db import (
    complete_import_batch,
    create_import_batch,
    fail_import_batch,
    get_htkd_engine,
)

DATASET_VERSION_ID = 9
RELEASE_ID = "2026-01"
IMPORT_PROGRAM = "htkd.importers.who_icd"

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
FOUNDATION_ROOT = "https://id.who.int/icd/entity"
MMS_ROOT = f"https://id.who.int/icd/release/11/{RELEASE_ID}/mms"

DEFAULT_LANGUAGE = "en"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_REQUEST_DELAY_SECONDS = 0.05
CHECKPOINT_EVERY_ENTITIES = 100
CHECKPOINT_DIR = (
    Path(__file__).resolve().parents[1] / "checkpoints"
)


@dataclass
class ImportStats:
    foundation_entities: int = 0
    foundation_texts: int = 0
    foundation_relationships: int = 0
    mms_entities: int = 0
    mms_texts: int = 0
    mms_index_terms: int = 0
    mms_postcoordination_rows: int = 0
    rejected: int = 0

    @property
    def source_row_count(self) -> int:
        return (
            self.foundation_entities
            + self.foundation_texts
            + self.foundation_relationships
            + self.mms_entities
            + self.mms_texts
            + self.mms_index_terms
            + self.mms_postcoordination_rows
            + self.rejected
        )

    @property
    def imported_row_count(self) -> int:
        return self.source_row_count - self.rejected


class WHOICDClient:
    def __init__(
        self,
        *,
        language: str = DEFAULT_LANGUAGE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    ) -> None:
        self.client_id = os.environ.get(
            "WHO_ICD_CLIENT_ID", ""
        ).strip()
        self.client_secret = os.environ.get(
            "WHO_ICD_CLIENT_SECRET", ""
        ).strip()

        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Set WHO_ICD_CLIENT_ID and WHO_ICD_CLIENT_SECRET "
                "in the shell environment."
            )

        self.language = language
        self.timeout_seconds = timeout_seconds
        self.request_delay_seconds = request_delay_seconds
        self.session = requests.Session()
        self._token: str | None = None

    def _authenticate(self) -> None:
        response = self.session.post(
            TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={
                "grant_type": "client_credentials",
                "scope": "icdapi_access",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self._authenticate()

        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Accept-Language": self.language,
            "API-Version": "v2",
        }

    def get_json(self, url: str) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(),
                    timeout=self.timeout_seconds,
                )

                if response.status_code == 401 and attempt < 3:
                    self._token = None
                    continue

                if (
                    response.status_code
                    in {429, 500, 502, 503, 504}
                    and attempt < 3
                ):
                    time.sleep(attempt * 2)
                    continue

                response.raise_for_status()

                if self.request_delay_seconds:
                    time.sleep(self.request_delay_seconds)

                return response.json()

            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(attempt * 2)

        assert last_error is not None
        raise last_error


def api_url(uri: str) -> str:
    if uri.startswith("http://id.who.int/"):
        return "https://" + uri[len("http://") :]
    return uri


def localized_value(
    value: Any,
) -> tuple[str | None, str | None]:
    if not isinstance(value, dict):
        return None, None

    language = value.get("@language")
    raw = value.get("@value")

    if raw is None:
        return language, None

    cleaned = str(raw).strip()
    return language, cleaned or None


def uri_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def upsert_foundation_entity(
    engine: Engine,
    *,
    dataset_version_id: int,
    payload: dict[str, Any],
) -> int:
    sql = text("""
        INSERT INTO terminology.who_icd_entity (
            dataset_version_id,
            foundation_uri,
            browser_url
        )
        VALUES (
            :dataset_version_id,
            :foundation_uri,
            :browser_url
        )
        ON CONFLICT (dataset_version_id, foundation_uri)
        DO UPDATE SET
            browser_url = EXCLUDED.browser_url
        RETURNING who_icd_entity_id
    """)

    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "dataset_version_id": dataset_version_id,
                    "foundation_uri": payload["@id"],
                    "browser_url": payload.get("browserUrl"),
                },
            ).scalar_one()
        )


def replace_foundation_text(
    engine: Engine,
    *,
    entity_id: int,
    payload: dict[str, Any],
) -> int:
    rows: list[dict[str, Any]] = []

    for field in (
        "title",
        "definition",
        "longDefinition",
        "fullySpecifiedName",
    ):
        language, value = localized_value(payload.get(field))
        if value:
            rows.append(
                {
                    "entity_id": entity_id,
                    "language": language or DEFAULT_LANGUAGE,
                    "text_type": field,
                    "text_value": value,
                }
            )

    for field in ("synonym", "inclusion", "exclusion"):
        values = payload.get(field)
        if not isinstance(values, list):
            continue

        for item in values:
            if not isinstance(item, dict):
                continue
            language, value = localized_value(
                item.get("label", item)
            )
            if value:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "language": language or DEFAULT_LANGUAGE,
                        "text_type": field,
                        "text_value": value,
                    }
                )

    with engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM terminology.who_icd_entity_text
                WHERE who_icd_entity_id = :entity_id
            """),
            {"entity_id": entity_id},
        )

        if rows:
            conn.execute(
                text("""
                    INSERT INTO terminology.who_icd_entity_text (
                        who_icd_entity_id,
                        language_code,
                        text_type,
                        text_value
                    )
                    VALUES (
                        :entity_id,
                        :language,
                        :text_type,
                        :text_value
                    )
                """),
                rows,
            )

    return len(rows)


def upsert_foundation_relationships(
    engine: Engine,
    *,
    dataset_version_id: int,
    payload: dict[str, Any],
) -> int:
    rows: list[dict[str, Any]] = []

    for relationship_type in ("parent", "child"):
        for target_uri in uri_list(payload.get(relationship_type)):
            rows.append(
                {
                    "dataset_version_id": dataset_version_id,
                    "source_uri": payload["@id"],
                    "relationship_type": relationship_type,
                    "target_uri": target_uri,
                }
            )

    if not rows:
        return 0

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO terminology.who_icd_relationship (
                    dataset_version_id,
                    source_foundation_uri,
                    relationship_type,
                    target_foundation_uri
                )
                VALUES (
                    :dataset_version_id,
                    :source_uri,
                    :relationship_type,
                    :target_uri
                )
                ON CONFLICT (
                    dataset_version_id,
                    source_foundation_uri,
                    relationship_type,
                    target_foundation_uri
                )
                DO NOTHING
            """),
            rows,
        )

    return len(rows)


def upsert_mms_entity(
    engine: Engine,
    *,
    dataset_version_id: int,
    payload: dict[str, Any],
) -> int:
    parents = uri_list(payload.get("parent"))

    with engine.begin() as conn:
        return int(
            conn.execute(
                text("""
                    INSERT INTO terminology.who_icd_mms_entity (
                        dataset_version_id,
                        mms_uri,
                        source_foundation_uri,
                        code,
                        class_kind,
                        browser_url,
                        parent_mms_uri
                    )
                    VALUES (
                        :dataset_version_id,
                        :mms_uri,
                        :source_uri,
                        :code,
                        :class_kind,
                        :browser_url,
                        :parent_uri
                    )
                    ON CONFLICT (dataset_version_id, mms_uri)
                    DO UPDATE SET
                        source_foundation_uri =
                            EXCLUDED.source_foundation_uri,
                        code = EXCLUDED.code,
                        class_kind = EXCLUDED.class_kind,
                        browser_url = EXCLUDED.browser_url,
                        parent_mms_uri = EXCLUDED.parent_mms_uri
                    RETURNING who_icd_mms_entity_id
                """),
                {
                    "dataset_version_id": dataset_version_id,
                    "mms_uri": payload["@id"],
                    "source_uri": payload.get("source"),
                    "code": payload.get("code"),
                    "class_kind": payload.get("classKind"),
                    "browser_url": payload.get("browserUrl"),
                    "parent_uri": parents[0] if parents else None,
                },
            ).scalar_one()
        )


def replace_mms_text(
    engine: Engine,
    *,
    entity_id: int,
    payload: dict[str, Any],
) -> int:
    rows: list[dict[str, Any]] = []

    for field in ("title", "definition", "longDefinition"):
        language, value = localized_value(payload.get(field))
        if value:
            rows.append(
                {
                    "entity_id": entity_id,
                    "language": language or DEFAULT_LANGUAGE,
                    "text_type": field,
                    "text_value": value,
                }
            )

    with engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM terminology.who_icd_mms_text
                WHERE who_icd_mms_entity_id = :entity_id
            """),
            {"entity_id": entity_id},
        )
        if rows:
            conn.execute(
                text("""
                    INSERT INTO terminology.who_icd_mms_text (
                        who_icd_mms_entity_id,
                        language_code,
                        text_type,
                        text_value
                    )
                    VALUES (
                        :entity_id,
                        :language,
                        :text_type,
                        :text_value
                    )
                """),
                rows,
            )

    return len(rows)


def replace_mms_index_terms(
    engine: Engine,
    *,
    entity_id: int,
    payload: dict[str, Any],
) -> int:
    rows: list[dict[str, Any]] = []

    values = payload.get("indexTerm")
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue

            language, value = localized_value(item.get("label"))
            if value:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "language": language or DEFAULT_LANGUAGE,
                        "term_text": value,
                        "foundation_reference_uri": item.get(
                            "foundationReference"
                        ),
                    }
                )

    with engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM terminology.who_icd_mms_index_term
                WHERE who_icd_mms_entity_id = :entity_id
            """),
            {"entity_id": entity_id},
        )
        if rows:
            conn.execute(
                text("""
                    INSERT INTO terminology.who_icd_mms_index_term (
                        who_icd_mms_entity_id,
                        language_code,
                        term_text,
                        foundation_reference_uri
                    )
                    VALUES (
                        :entity_id,
                        :language,
                        :term_text,
                        :foundation_reference_uri
                    )
                """),
                rows,
            )

    return len(rows)


def replace_mms_postcoordination(
    engine: Engine,
    *,
    entity_id: int,
    payload: dict[str, Any],
) -> int:
    rows: list[dict[str, Any]] = []

    scales = payload.get("postcoordinationScale")
    if isinstance(scales, list):
        for scale in scales:
            if not isinstance(scale, dict):
                continue

            scale_entities = uri_list(scale.get("scaleEntity"))
            if not scale_entities:
                scale_entities = [None]

            raw_required = scale.get("requiredPostcoordination")
            if isinstance(raw_required, str):
                required = raw_required.lower() == "true"
            elif isinstance(raw_required, bool):
                required = raw_required
            else:
                required = None

            for scale_entity_uri in scale_entities:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "scale_uri": scale.get("@id"),
                        "axis_name_uri": scale.get("axisName"),
                        "required": required,
                        "allow_multiple": scale.get(
                            "allowMultipleValues"
                        ),
                        "scale_entity_uri": scale_entity_uri,
                    }
                )

    with engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM
                    terminology.who_icd_mms_postcoordination
                WHERE who_icd_mms_entity_id = :entity_id
            """),
            {"entity_id": entity_id},
        )
        if rows:
            conn.execute(
                text("""
                    INSERT INTO
                        terminology.who_icd_mms_postcoordination (
                            who_icd_mms_entity_id,
                            scale_uri,
                            axis_name_uri,
                            required_postcoordination,
                            allow_multiple_values,
                            scale_entity_uri
                        )
                    VALUES (
                        :entity_id,
                        :scale_uri,
                        :axis_name_uri,
                        :required,
                        :allow_multiple,
                        :scale_entity_uri
                    )
                """),
                rows,
            )

    return len(rows)



def checkpoint_path(
    *,
    dataset_version_id: int,
    language: str,
) -> Path:
    safe_language = language.replace("/", "_")
    return CHECKPOINT_DIR / (
        f"who_icd_{RELEASE_ID}_"
        f"dv{dataset_version_id}_{safe_language}.json"
    )


def save_checkpoint(
    path: Path,
    *,
    phase: str,
    queue: deque[str],
    seen: set[str],
    foundation_complete: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "release_id": RELEASE_ID,
        "dataset_version_id": DATASET_VERSION_ID,
        "phase": phase,
        "foundation_complete": foundation_complete,
        "seen": sorted(seen),
        "queue": list(queue),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_path.replace(path)


def load_checkpoint(
    path: Path,
    *,
    dataset_version_id: int,
) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"WHO ICD checkpoint not found: {path}"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("release_id") != RELEASE_ID:
        raise RuntimeError(
            "Checkpoint release does not match this importer: "
            f"{payload.get('release_id')} != {RELEASE_ID}"
        )

    stored_version = payload.get("dataset_version_id")
    if stored_version not in {None, dataset_version_id}:
        raise RuntimeError(
            "Checkpoint dataset version does not match: "
            f"{stored_version} != {dataset_version_id}"
        )

    return payload


def load_existing_uris(
    engine: Engine,
    *,
    dataset_version_id: int,
    phase: str,
) -> set[str]:
    if phase == "foundation":
        sql = text("""
            SELECT foundation_uri
            FROM terminology.who_icd_entity
            WHERE dataset_version_id = :dataset_version_id
        """)
    elif phase == "mms":
        sql = text("""
            SELECT mms_uri
            FROM terminology.who_icd_mms_entity
            WHERE dataset_version_id = :dataset_version_id
        """)
    else:
        raise ValueError(f"Unknown WHO ICD phase: {phase}")

    with engine.connect() as conn:
        return {
            str(row[0])
            for row in conn.execute(
                sql,
                {"dataset_version_id": dataset_version_id},
            )
            if row[0]
        }


def mark_batch_interrupted(
    engine: Engine,
    *,
    import_batch_id: int,
    note: str,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE control.import_batch
                SET
                    import_status = 'interrupted',
                    completed_at = NOW(),
                    notes = CASE
                        WHEN notes IS NULL OR notes = ''
                            THEN :note
                        ELSE notes || E'\n' || :note
                    END
                WHERE import_batch_id = :import_batch_id
            """),
            {
                "import_batch_id": import_batch_id,
                "note": note,
            },
        )


def import_foundation(
    engine: Engine,
    client: WHOICDClient,
    stats: ImportStats,
    *,
    dataset_version_id: int,
    max_entities: int | None,
    checkpoint: Path,
    resume_state: dict[str, Any] | None = None,
    recover_existing: bool = False,
) -> None:
    if resume_state is not None:
        queue = deque(
            str(item)
            for item in resume_state.get("queue", [])
        )
        seen = {
            str(item)
            for item in resume_state.get("seen", [])
        }
        print(
            f"Foundation resume: {len(seen):,} seen; "
            f"{len(queue):,} queued"
        )
    else:
        root = client.get_json(FOUNDATION_ROOT)
        queue = deque(uri_list(root.get("child")))
        seen: set[str] = set()

    existing = (
        load_existing_uris(
            engine,
            dataset_version_id=dataset_version_id,
            phase="foundation",
        )
        if recover_existing
        else set()
    )

    if recover_existing:
        print(
            f"Foundation recovery: "
            f"{len(existing):,} existing DB entities"
        )

    while queue:
        if max_entities is not None and len(seen) >= max_entities:
            break

        uri = queue.popleft()

        if uri in seen:
            continue

        try:
            payload = client.get_json(api_url(uri))
            if not payload.get("@id"):
                raise ValueError("Foundation entity has no @id")

            # Recovery still fetches existing entities so their child
            # frontier can be reconstructed, but avoids rewriting them.
            if uri not in existing:
                entity_id = upsert_foundation_entity(
                    engine,
                    dataset_version_id=dataset_version_id,
                    payload=payload,
                )
                stats.foundation_entities += 1
                stats.foundation_texts += replace_foundation_text(
                    engine,
                    entity_id=entity_id,
                    payload=payload,
                )
                stats.foundation_relationships += (
                    upsert_foundation_relationships(
                        engine,
                        dataset_version_id=dataset_version_id,
                        payload=payload,
                    )
                )

            for child in uri_list(payload.get("child")):
                if child not in seen:
                    queue.append(child)

            seen.add(uri)

            if len(seen) % CHECKPOINT_EVERY_ENTITIES == 0:
                save_checkpoint(
                    checkpoint,
                    phase="foundation",
                    queue=queue,
                    seen=seen,
                    foundation_complete=False,
                )
                print(
                    f"Foundation     : "
                    f"{len(seen):,} entities"
                )

        except KeyboardInterrupt:
            queue.appendleft(uri)
            save_checkpoint(
                checkpoint,
                phase="foundation",
                queue=queue,
                seen=seen,
                foundation_complete=False,
            )
            raise
        except Exception as exc:
            stats.rejected += 1
            seen.add(uri)
            print(f"Foundation warning: {uri}: {exc}")

    save_checkpoint(
        checkpoint,
        phase="mms",
        queue=deque(),
        seen=set(),
        foundation_complete=True,
    )


def import_mms(
    engine: Engine,
    client: WHOICDClient,
    stats: ImportStats,
    *,
    dataset_version_id: int,
    max_entities: int | None,
    checkpoint: Path,
    resume_state: dict[str, Any] | None = None,
    recover_existing: bool = False,
) -> None:
    if resume_state is not None:
        queue = deque(
            str(item)
            for item in resume_state.get("queue", [])
        )
        seen = {
            str(item)
            for item in resume_state.get("seen", [])
        }

        # A checkpoint written at the Foundation/MMS boundary has an
        # intentionally empty MMS queue. Initialize it from the MMS root.
        if not queue and not seen:
            root = client.get_json(MMS_ROOT)
            queue = deque(uri_list(root.get("child")))

        print(
            f"MMS resume       : {len(seen):,} seen; "
            f"{len(queue):,} queued"
        )
    else:
        root = client.get_json(MMS_ROOT)
        queue = deque(uri_list(root.get("child")))
        seen: set[str] = set()

    if not queue:
        raise RuntimeError(
            "WHO MMS root did not expose a child list. "
            "Inspect the current MMS root JSON before changing "
            "the traversal logic."
        )

    existing = (
        load_existing_uris(
            engine,
            dataset_version_id=dataset_version_id,
            phase="mms",
        )
        if recover_existing
        else set()
    )

    if recover_existing:
        print(
            f"MMS recovery     : "
            f"{len(existing):,} existing DB entities"
        )

    while queue:
        if max_entities is not None and len(seen) >= max_entities:
            break

        uri = queue.popleft()

        if uri in seen:
            continue

        try:
            payload = client.get_json(api_url(uri))
            if not payload.get("@id"):
                raise ValueError("MMS entity has no @id")

            # For the first recovery after the old interrupted run,
            # existing rows are not rewritten. We still fetch them to
            # discover their children and rebuild the traversal frontier.
            if uri not in existing:
                entity_id = upsert_mms_entity(
                    engine,
                    dataset_version_id=dataset_version_id,
                    payload=payload,
                )
                stats.mms_entities += 1
                stats.mms_texts += replace_mms_text(
                    engine,
                    entity_id=entity_id,
                    payload=payload,
                )
                stats.mms_index_terms += replace_mms_index_terms(
                    engine,
                    entity_id=entity_id,
                    payload=payload,
                )
                stats.mms_postcoordination_rows += (
                    replace_mms_postcoordination(
                        engine,
                        entity_id=entity_id,
                        payload=payload,
                    )
                )

            for child in uri_list(payload.get("child")):
                if child not in seen:
                    queue.append(child)

            seen.add(uri)

            if len(seen) % CHECKPOINT_EVERY_ENTITIES == 0:
                save_checkpoint(
                    checkpoint,
                    phase="mms",
                    queue=queue,
                    seen=seen,
                    foundation_complete=True,
                )
                print(
                    f"MMS            : "
                    f"{len(seen):,} entities"
                )

        except KeyboardInterrupt:
            queue.appendleft(uri)
            save_checkpoint(
                checkpoint,
                phase="mms",
                queue=queue,
                seen=seen,
                foundation_complete=True,
            )
            raise
        except Exception as exc:
            stats.rejected += 1
            seen.add(uri)
            print(f"MMS warning    : {uri}: {exc}")

    save_checkpoint(
        checkpoint,
        phase="complete",
        queue=deque(),
        seen=seen,
        foundation_complete=True,
    )


def import_who_icd(
    *,
    environment: str = "MacBook",
    dataset_version_id: int = DATASET_VERSION_ID,
    language: str = DEFAULT_LANGUAGE,
    max_foundation_entities: int | None = None,
    max_mms_entities: int | None = None,
    resume: bool = False,
    recover_existing: bool = False,
    skip_foundation: bool = False,
) -> None:
    engine = get_htkd_engine(environment)
    client = WHOICDClient(language=language)
    stats = ImportStats()

    checkpoint = checkpoint_path(
        dataset_version_id=dataset_version_id,
        language=language,
    )

    resume_state: dict[str, Any] | None = None
    if resume:
        resume_state = load_checkpoint(
            checkpoint,
            dataset_version_id=dataset_version_id,
        )

    print(f"Environment    : {environment}")
    print(f"Dataset version: {dataset_version_id}")
    print(f"WHO release    : {RELEASE_ID}")
    print(f"Language       : {language}")
    print(f"Checkpoint     : {checkpoint}")
    print(f"Resume         : {resume}")
    print(f"Recover DB     : {recover_existing}")
    print(f"Skip Foundation: {skip_foundation}")

    import_batch_id = create_import_batch(
        engine,
        dataset_version_id=dataset_version_id,
        source_checksum=None,
        import_program=IMPORT_PROGRAM,
        notes=(
            f"WHO ICD API release {RELEASE_ID}; "
            f"language={language}; Foundation + ICD-11 MMS; "
            f"resume={resume}; recover_existing={recover_existing}; "
            f"skip_foundation={skip_foundation}"
        ),
    )

    print(f"Import batch   : {import_batch_id}")

    try:
        phase = (
            str(resume_state.get("phase"))
            if resume_state is not None
            else None
        )

        foundation_complete = bool(
            resume_state
            and resume_state.get("foundation_complete")
        )

        if skip_foundation or foundation_complete:
            print("\nFoundation already complete; skipping.")
        elif phase == "foundation":
            print("\nResuming WHO Foundation...")
            import_foundation(
                engine,
                client,
                stats,
                dataset_version_id=dataset_version_id,
                max_entities=max_foundation_entities,
                checkpoint=checkpoint,
                resume_state=resume_state,
                recover_existing=recover_existing,
            )
        else:
            print("\nImporting WHO Foundation...")
            import_foundation(
                engine,
                client,
                stats,
                dataset_version_id=dataset_version_id,
                max_entities=max_foundation_entities,
                checkpoint=checkpoint,
                recover_existing=recover_existing,
            )

        # If the old run was interrupted before checkpoints existed,
        # --skip-foundation --recover-existing is the intended recovery
        # path: preserve the completed Foundation and rebuild the MMS
        # frontier from the API while avoiding rewrites of existing rows.
        mms_resume_state = None
        if resume_state is not None and phase == "mms":
            mms_resume_state = resume_state
        elif resume_state is not None and phase == "complete":
            print("\nCheckpoint says WHO ICD import is complete.")
            mms_resume_state = resume_state

        if phase == "complete":
            pass
        else:
            print("\nImporting ICD-11 MMS...")
            import_mms(
                engine,
                client,
                stats,
                dataset_version_id=dataset_version_id,
                max_entities=max_mms_entities,
                checkpoint=checkpoint,
                resume_state=mms_resume_state,
                recover_existing=recover_existing,
            )

        complete_import_batch(
            engine,
            import_batch_id=import_batch_id,
            source_row_count=stats.source_row_count,
            imported_row_count=stats.imported_row_count,
            rejected_row_count=stats.rejected,
        )

    except KeyboardInterrupt:
        note = (
            "Interrupted by user. WHO ICD traversal checkpoint "
            f"saved at {checkpoint}."
        )
        mark_batch_interrupted(
            engine,
            import_batch_id=import_batch_id,
            note=note,
        )
        print("\nWHO ICD import interrupted safely.")
        print(f"Checkpoint saved: {checkpoint}")
        print(
            "Resume later with: "
            "python -m htkd.importers.who_icd "
            "--environment MacBook --resume"
        )
        return

    except Exception as exc:
        fail_import_batch(
            engine,
            import_batch_id=import_batch_id,
            error_message=str(exc),
        )
        raise

    print("\nWHO ICD import completed.")
    print(
        f"Foundation entities written this run: "
        f"{stats.foundation_entities:,}"
    )
    print(
        f"Foundation text rows written this run: "
        f"{stats.foundation_texts:,}"
    )
    print(
        f"Foundation relationships written this run: "
        f"{stats.foundation_relationships:,}"
    )
    print(
        f"MMS entities written this run      : "
        f"{stats.mms_entities:,}"
    )
    print(
        f"MMS text rows written this run     : "
        f"{stats.mms_texts:,}"
    )
    print(
        f"MMS index terms written this run   : "
        f"{stats.mms_index_terms:,}"
    )
    print(
        f"MMS postcoordination written this run: "
        f"{stats.mms_postcoordination_rows:,}"
    )
    print(f"Rejected/API errors                : {stats.rejected:,}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import WHO ICD-11 Foundation and MMS into HTKD."
        )
    )

    parser.add_argument(
        "--environment",
        default="MacBook",
        choices=["MacBook", "iMac", "NRI Notebook"],
    )
    parser.add_argument(
        "--dataset-version-id",
        type=int,
        default=DATASET_VERSION_ID,
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
    )
    parser.add_argument(
        "--max-foundation-entities",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--max-mms-entities",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the saved WHO ICD traversal checkpoint.",
    )
    parser.add_argument(
        "--recover-existing",
        action="store_true",
        help=(
            "Use existing WHO ICD rows to recover from a pre-checkpoint "
            "interrupted run. Existing entities are fetched for traversal "
            "but are not rewritten."
        ),
    )
    parser.add_argument(
        "--skip-foundation",
        action="store_true",
        help=(
            "Skip Foundation import. Use only when Foundation for this "
            "dataset version is already complete."
        ),
    )

    args = parser.parse_args()

    import_who_icd(
        environment=args.environment,
        dataset_version_id=args.dataset_version_id,
        language=args.language,
        max_foundation_entities=args.max_foundation_entities,
        max_mms_entities=args.max_mms_entities,
        resume=args.resume,
        recover_existing=args.recover_existing,
        skip_foundation=args.skip_foundation,
    )


if __name__ == "__main__":
    main()


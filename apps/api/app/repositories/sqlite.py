from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from app.models.claim import PaperClaim
from app.models.contradiction import ContradictionPair
from app.models.paper import Paper
from app.models.report import AnalysisReport, SearchRun


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS papers (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        doi TEXT,
                        title TEXT NOT NULL,
                        year INTEGER,
                        raw_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(source, external_id)
                    );

                    CREATE TABLE IF NOT EXISTS search_runs (
                        id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        raw_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS search_run_papers (
                        search_run_id TEXT NOT NULL,
                        paper_id TEXT NOT NULL,
                        PRIMARY KEY (search_run_id, paper_id),
                        FOREIGN KEY(search_run_id) REFERENCES search_runs(id) ON DELETE CASCADE,
                        FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS claims (
                        paper_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL DEFAULT '',
                        claim TEXT NOT NULL,
                        direction TEXT,
                        confidence REAL NOT NULL,
                        quality REAL NOT NULL,
                        raw_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (paper_id, provider, model),
                        FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS contradiction_cache (
                        pair_key TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL DEFAULT '',
                        raw_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (pair_key, provider, model)
                    );

                    CREATE TABLE IF NOT EXISTS reports (
                        id TEXT PRIMARY KEY,
                        search_run_id TEXT,
                        query TEXT,
                        provider TEXT NOT NULL,
                        model TEXT,
                        raw_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                connection.commit()

    @staticmethod
    def _dump_model(model: object) -> str:
        payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def upsert_papers(self, papers: list[Paper]) -> None:
        if not papers:
            return

        rows = [
            (
                paper.id,
                paper.source,
                paper.external_id,
                paper.doi,
                paper.title,
                paper.year,
                self._dump_model(paper),
                paper.created_at.isoformat(),
            )
            for paper in papers
        ]

        with self._lock:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT INTO papers (id, source, external_id, doi, title, year, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        doi = excluded.doi,
                        title = excluded.title,
                        year = excluded.year,
                        raw_json = excluded.raw_json,
                        updated_at = excluded.updated_at
                    """,
                    rows,
                )
                connection.commit()

    def get_papers(self, paper_ids: list[str]) -> list[Paper]:
        if not paper_ids:
            return []

        placeholders = ",".join("?" for _ in paper_ids)
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    f"SELECT id, raw_json FROM papers WHERE id IN ({placeholders})",
                    paper_ids,
                ).fetchall()

        mapped = {row["id"]: Paper.model_validate_json(row["raw_json"]) for row in rows}
        return [mapped[paper_id] for paper_id in paper_ids if paper_id in mapped]

    def save_search_run(self, search_run: SearchRun, papers: list[Paper]) -> None:
        self.upsert_papers(papers)
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO search_runs (id, query, raw_json, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        query = excluded.query,
                        raw_json = excluded.raw_json,
                        created_at = excluded.created_at
                    """,
                    (
                        search_run.id,
                        search_run.query,
                        self._dump_model(search_run),
                        search_run.created_at.isoformat(),
                    ),
                )
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO search_run_papers (search_run_id, paper_id)
                    VALUES (?, ?)
                    """,
                    [(search_run.id, paper.id) for paper in papers],
                )
                connection.commit()

    def save_claims(self, claims: list[PaperClaim]) -> None:
        if not claims:
            return

        rows = [
            (
                claim.paper_id,
                claim.provider,
                claim.model or "",
                claim.claim,
                claim.direction.value if claim.direction else None,
                claim.confidence,
                claim.quality,
                self._dump_model(claim),
                claim.updated_at.isoformat(),
            )
            for claim in claims
        ]

        with self._lock:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT INTO claims (
                        paper_id, provider, model, claim, direction, confidence, quality, raw_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(paper_id, provider, model) DO UPDATE SET
                        claim = excluded.claim,
                        direction = excluded.direction,
                        confidence = excluded.confidence,
                        quality = excluded.quality,
                        raw_json = excluded.raw_json,
                        updated_at = excluded.updated_at
                    """,
                    rows,
                )
                connection.commit()

    def get_claims(self, paper_ids: list[str], provider: str, model: str | None) -> dict[str, PaperClaim]:
        if not paper_ids:
            return {}

        placeholders = ",".join("?" for _ in paper_ids)
        normalized_model = model or ""
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT paper_id, raw_json
                    FROM claims
                    WHERE provider = ? AND model = ? AND paper_id IN ({placeholders})
                    """,
                    [provider, normalized_model, *paper_ids],
                ).fetchall()

        return {row["paper_id"]: PaperClaim.model_validate_json(row["raw_json"]) for row in rows}

    def get_cached_contradiction(
        self, pair_key: str, provider: str, model: str | None
    ) -> ContradictionPair | None:
        normalized_model = model or ""
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT raw_json
                    FROM contradiction_cache
                    WHERE pair_key = ? AND provider = ? AND model = ?
                    """,
                    (pair_key, provider, normalized_model),
                ).fetchone()

        if row is None:
            return None
        return ContradictionPair.model_validate_json(row["raw_json"])

    def save_cached_contradiction(
        self, pair_key: str, provider: str, model: str | None, contradiction: ContradictionPair
    ) -> None:
        normalized_model = model or ""
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO contradiction_cache (pair_key, provider, model, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(pair_key, provider, model) DO UPDATE SET
                        raw_json = excluded.raw_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        pair_key,
                        provider,
                        normalized_model,
                        self._dump_model(contradiction),
                        contradiction.updated_at.isoformat(),
                    ),
                )
                connection.commit()

    def save_report(self, report: AnalysisReport) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO reports (id, search_run_id, query, provider, model, raw_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        search_run_id = excluded.search_run_id,
                        query = excluded.query,
                        provider = excluded.provider,
                        model = excluded.model,
                        raw_json = excluded.raw_json,
                        created_at = excluded.created_at
                    """,
                    (
                        report.id,
                        report.search_run_id,
                        report.query,
                        report.provider,
                        report.model,
                        self._dump_model(report),
                        report.created_at.isoformat(),
                    ),
                )
                connection.commit()

    def get_report(self, report_id: str) -> AnalysisReport | None:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT raw_json FROM reports WHERE id = ?",
                    (report_id,),
                ).fetchone()

        if row is None:
            return None
        return AnalysisReport.model_validate_json(row["raw_json"])


from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.models.claim import PaperClaim
from app.models.contradiction import (
    ContradictionMode,
    ContradictionPair,
    build_pair_key,
)
from app.models.paper import Paper, build_query_cache_key
from app.models.report import AnalysisJob, AnalysisReport, JobStatus, SearchRun

ACTIVE_JOB_STATUSES = {
    JobStatus.pending,
    JobStatus.running,
    JobStatus.ingesting,
    JobStatus.embedding,
    JobStatus.analyzing,
}


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
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute("PRAGMA cache_size=-64000;")
        connection.execute("PRAGMA temp_store=MEMORY;")
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

                    CREATE INDEX IF NOT EXISTS idx_search_runs_query ON search_runs(query);

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
                        claim TEXT,
                        direction TEXT,
                        confidence REAL NOT NULL,
                        quality REAL NOT NULL,
                        raw_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (paper_id, provider, model),
                        FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS contradictions (
                        pair_key TEXT PRIMARY KEY,
                        paper_a_id TEXT NOT NULL,
                        paper_b_id TEXT NOT NULL,
                        provider TEXT,
                        model TEXT,
                        score REAL NOT NULL,
                        raw_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(paper_a_id) REFERENCES papers(id) ON DELETE CASCADE,
                        FOREIGN KEY(paper_b_id) REFERENCES papers(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS reports (
                        id TEXT PRIMARY KEY,
                        query TEXT,
                        provider TEXT NOT NULL,
                        model TEXT,
                        raw_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS analysis_jobs (
                        id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        normalized_query TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        paper_count INTEGER NOT NULL,
                        extracted_claim_count INTEGER NOT NULL,
                        skipped_claim_count INTEGER NOT NULL,
                        cluster_count INTEGER NOT NULL,
                        filtered_pair_count INTEGER NOT NULL,
                        scored_pair_count INTEGER NOT NULL,
                        contradiction_count INTEGER NOT NULL,
                        cached_pair_count INTEGER NOT NULL,
                        has_contradictions INTEGER NOT NULL,
                        error TEXT,
                        raw_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        completed_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS job_papers (
                        job_id TEXT NOT NULL,
                        paper_id TEXT NOT NULL,
                        PRIMARY KEY (job_id, paper_id),
                        FOREIGN KEY(job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE,
                        FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS job_contradictions (
                        job_id TEXT NOT NULL,
                        pair_key TEXT NOT NULL,
                        kind TEXT NOT NULL DEFAULT 'contradiction',
                        PRIMARY KEY (job_id, pair_key, kind),
                        FOREIGN KEY(job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE,
                        FOREIGN KEY(pair_key) REFERENCES contradictions(pair_key) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS query_cache (
                        query_hash TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        raw_results TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                connection.commit()

    @staticmethod
    def _dump_model(model: object) -> str:
        payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _dump_json(payload: Any) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

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

    def get_popular_queries(self, prefix: str, limit: int) -> list[dict]:
        with self._lock:
            with self._connect() as connection:
                if not prefix:
                    rows = connection.execute(
                        "SELECT LOWER(query) as query, COUNT(*) as count FROM search_runs WHERE TRIM(query) != '' GROUP BY LOWER(query) ORDER BY count DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT LOWER(query) as query, COUNT(*) as count FROM search_runs WHERE LOWER(query) LIKE ? AND TRIM(query) != '' GROUP BY LOWER(query) ORDER BY count DESC LIMIT ?",
                        (f"%{prefix.lower()}%", limit),
                    ).fetchall()
        return [{"query": row["query"], "count": row["count"]} for row in rows]

    def get_query_cache(
        self, query: str, source: str, freshness_hours: int
    ) -> list[Paper] | None:
        key = build_query_cache_key(query, source)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT raw_results, created_at
                    FROM query_cache
                    WHERE query_hash = ? AND source = ?
                    """,
                    (key, source),
                ).fetchone()

        if row is None:
            return None
        created_at = self._parse_dt(row["created_at"])
        if created_at is None or created_at < cutoff:
            return None
        payload = json.loads(row["raw_results"])
        return [Paper.model_validate(item) for item in payload]

    def save_query_cache(self, query: str, source: str, papers: list[Paper]) -> None:
        key = build_query_cache_key(query, source)
        created_at = datetime.now(timezone.utc).isoformat()
        payload = [paper.model_dump(mode="json") for paper in papers]
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO query_cache (query_hash, source, raw_results, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(query_hash) DO UPDATE SET
                        source = excluded.source,
                        raw_results = excluded.raw_results,
                        created_at = excluded.created_at
                    """,
                    (key, source, self._dump_json(payload), created_at),
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
                claim.claim or "",
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

    def get_claims(
        self, paper_ids: list[str], provider: str, model: str | None
    ) -> dict[str, PaperClaim]:
        return self.get_best_claims(paper_ids)

    def get_best_claims(self, paper_ids: list[str]) -> dict[str, PaperClaim]:
        if not paper_ids:
            return {}

        placeholders = ",".join("?" for _ in paper_ids)
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT paper_id, raw_json
                    FROM claims
                    WHERE paper_id IN ({placeholders})
                    ORDER BY quality DESC, confidence DESC, updated_at DESC
                    """,
                    paper_ids,
                ).fetchall()

        best: dict[str, PaperClaim] = {}
        for row in rows:
            claim = PaperClaim.model_validate_json(row["raw_json"])
            if row["paper_id"] not in best and claim.claim:
                best[row["paper_id"]] = claim
        return best

    def get_cached_contradiction(
        self, paper_a_id: str, paper_b_id: str
    ) -> ContradictionPair | None:
        pair_key = build_pair_key(paper_a_id, paper_b_id)
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT raw_json
                    FROM contradictions
                    WHERE pair_key = ?
                    """,
                    (pair_key,),
                ).fetchone()

        if row is None:
            return None
        return ContradictionPair.model_validate_json(row["raw_json"])

    def save_contradiction(
        self,
        contradiction: ContradictionPair,
        job_id: str | None = None,
        kind: str = "contradiction",
    ) -> bool:
        pair_key = contradiction.pair_key or build_pair_key(
            contradiction.paper_a_id, contradiction.paper_b_id
        )
        contradiction.pair_key = pair_key

        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT raw_json FROM contradictions WHERE pair_key = ?",
                    (pair_key,),
                ).fetchone()
                if existing is not None:
                    stored = ContradictionPair.model_validate_json(existing["raw_json"])
                    if contradiction.score <= stored.score:
                        if job_id:
                            job_exists = connection.execute(
                                "SELECT 1 FROM analysis_jobs WHERE id = ?",
                                (job_id,),
                            ).fetchone()
                            if job_exists is not None:
                                connection.execute(
                                    """
                                    INSERT OR REPLACE INTO job_contradictions (job_id, pair_key, kind)
                                    VALUES (?, ?, ?)
                                    """,
                                    (job_id, pair_key, kind),
                                )
                            connection.commit()
                        return False

                connection.execute(
                    """
                    INSERT INTO contradictions (pair_key, paper_a_id, paper_b_id, provider, model, score, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(pair_key) DO UPDATE SET
                        paper_a_id = excluded.paper_a_id,
                        paper_b_id = excluded.paper_b_id,
                        provider = excluded.provider,
                        model = excluded.model,
                        score = excluded.score,
                        raw_json = excluded.raw_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        pair_key,
                        contradiction.paper_a_id,
                        contradiction.paper_b_id,
                        contradiction.provider,
                        contradiction.model,
                        contradiction.score,
                        self._dump_model(contradiction),
                        contradiction.updated_at.isoformat(),
                    ),
                )
                if job_id:
                    job_exists = connection.execute(
                        "SELECT 1 FROM analysis_jobs WHERE id = ?",
                        (job_id,),
                    ).fetchone()
                    if job_exists is not None:
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO job_contradictions (job_id, pair_key, kind)
                            VALUES (?, ?, ?)
                            """,
                            (job_id, pair_key, kind),
                        )
                connection.commit()
        return True

    def save_report(self, report: AnalysisReport) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO reports (id, query, provider, model, raw_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        query = excluded.query,
                        provider = excluded.provider,
                        model = excluded.model,
                        raw_json = excluded.raw_json,
                        created_at = excluded.created_at
                    """,
                    (
                        report.id,
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

    def create_job(self, job: AnalysisJob) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO analysis_jobs (
                        id, query, normalized_query, status, progress, paper_count,
                        extracted_claim_count, skipped_claim_count, cluster_count,
                        filtered_pair_count, scored_pair_count, contradiction_count,
                        cached_pair_count, has_contradictions, error, raw_json,
                        created_at, updated_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        query = excluded.query,
                        normalized_query = excluded.normalized_query,
                        status = excluded.status,
                        progress = excluded.progress,
                        paper_count = excluded.paper_count,
                        extracted_claim_count = excluded.extracted_claim_count,
                        skipped_claim_count = excluded.skipped_claim_count,
                        cluster_count = excluded.cluster_count,
                        filtered_pair_count = excluded.filtered_pair_count,
                        scored_pair_count = excluded.scored_pair_count,
                        contradiction_count = excluded.contradiction_count,
                        cached_pair_count = excluded.cached_pair_count,
                        has_contradictions = excluded.has_contradictions,
                        error = excluded.error,
                        raw_json = excluded.raw_json,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        completed_at = excluded.completed_at
                    """,
                    self._job_row(job),
                )
                connection.commit()

    def _job_row(self, job: AnalysisJob) -> tuple[Any, ...]:
        return (
            job.id,
            job.query,
            job.normalized_query,
            job.status.value,
            job.progress,
            job.paper_count,
            job.extracted_claim_count,
            job.skipped_claim_count,
            job.cluster_count,
            job.filtered_pair_count,
            job.scored_pair_count,
            job.contradiction_count,
            job.cached_pair_count,
            1 if job.has_contradictions else 0,
            job.error,
            self._dump_model(job),
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            job.completed_at.isoformat() if job.completed_at else None,
        )

    def get_job(self, job_id: str) -> AnalysisJob | None:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT raw_json FROM analysis_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
        if row is None:
            return None
        return AnalysisJob.model_validate_json(row["raw_json"])

    def update_job(self, job: AnalysisJob) -> None:
        job.updated_at = datetime.now(timezone.utc)
        self.create_job(job)

    def get_recent_completed_job(
        self, normalized_query: str, within_hours: int
    ) -> AnalysisJob | None:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=within_hours)
        ).isoformat()
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT raw_json
                    FROM analysis_jobs
                    WHERE normalized_query = ? AND status = ? AND completed_at IS NOT NULL AND completed_at >= ?
                    ORDER BY completed_at DESC
                    """,
                    (normalized_query, JobStatus.done.value, cutoff),
                ).fetchall()

        for row in rows:
            job = AnalysisJob.model_validate_json(row["raw_json"])
            if job.mode == ContradictionMode.corpus_vs_corpus:
                return job
        return None

    def get_recent_active_job(
        self, normalized_query: str, mode: ContradictionMode
    ) -> AnalysisJob | None:
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT raw_json
                    FROM analysis_jobs
                    WHERE normalized_query = ?
                    ORDER BY updated_at DESC
                    """,
                    (normalized_query,),
                ).fetchall()

        for row in rows:
            job = AnalysisJob.model_validate_json(row["raw_json"])
            if job.mode != mode:
                continue
            if job.status in ACTIVE_JOB_STATUSES:
                return job
        return None

    def link_job_papers(self, job_id: str, paper_ids: list[str]) -> None:
        if not paper_ids:
            return
        with self._lock:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO job_papers (job_id, paper_id)
                    VALUES (?, ?)
                    """,
                    [(job_id, paper_id) for paper_id in paper_ids],
                )
                connection.commit()

    def get_job_papers(self, job_id: str) -> list[Paper]:
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT p.raw_json
                    FROM job_papers jp
                    INNER JOIN papers p ON p.id = jp.paper_id
                    WHERE jp.job_id = ?
                    ORDER BY p.year DESC, p.title ASC
                    """,
                    (job_id,),
                ).fetchall()
        return [Paper.model_validate_json(row["raw_json"]) for row in rows]

    def list_job_contradictions(
        self, job_id: str, kind: str | None = None
    ) -> list[ContradictionPair]:
        query = """
            SELECT c.raw_json
            FROM job_contradictions jc
            INNER JOIN contradictions c ON c.pair_key = jc.pair_key
            WHERE jc.job_id = ?
        """
        params: list[Any] = [job_id]
        if kind is not None:
            query += " AND jc.kind = ?"
            params.append(kind)
        query += " ORDER BY c.score DESC, c.updated_at DESC"
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(query, params).fetchall()
        return [ContradictionPair.model_validate_json(row["raw_json"]) for row in rows]

    def expire_stale_running_jobs(self, timeout_minutes: int) -> list[str]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        ).isoformat()
        expired_ids: list[str] = []
        with self._lock:
            with self._connect() as connection:
                placeholders = ",".join("?" for _ in ACTIVE_JOB_STATUSES)
                rows = connection.execute(
                    f"""
                    SELECT raw_json
                    FROM analysis_jobs
                    WHERE status IN ({placeholders}) AND created_at < ?
                    """,
                    [status.value for status in ACTIVE_JOB_STATUSES] + [cutoff],
                ).fetchall()
                for row in rows:
                    job = AnalysisJob.model_validate_json(row["raw_json"])
                    job.status = JobStatus.failed
                    job.error = "job_timeout_exceeded"
                    job.completed_at = datetime.now(timezone.utc)
                    job.progress = max(job.progress, 95)
                    connection.execute(
                        """
                        UPDATE analysis_jobs
                        SET status = ?, error = ?, progress = ?, raw_json = ?, updated_at = ?, completed_at = ?
                        WHERE id = ?
                        """,
                        (
                            job.status.value,
                            job.error,
                            job.progress,
                            self._dump_model(job),
                            datetime.now(timezone.utc).isoformat(),
                            job.completed_at.isoformat(),
                            job.id,
                        ),
                    )
                    expired_ids.append(job.id)
                connection.commit()
        return expired_ids

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT raw_json FROM analysis_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return False

                pair_rows = connection.execute(
                    "SELECT pair_key FROM job_contradictions WHERE job_id = ?",
                    (job_id,),
                ).fetchall()
                paper_rows = connection.execute(
                    "SELECT paper_id FROM job_papers WHERE job_id = ?",
                    (job_id,),
                ).fetchall()

                connection.execute("DELETE FROM reports WHERE id = ?", (job_id,))
                connection.execute(
                    "DELETE FROM job_contradictions WHERE job_id = ?", (job_id,)
                )
                connection.execute("DELETE FROM job_papers WHERE job_id = ?", (job_id,))
                connection.execute("DELETE FROM analysis_jobs WHERE id = ?", (job_id,))

                for pair_row in pair_rows:
                    reference_count = connection.execute(
                        "SELECT COUNT(*) AS count FROM job_contradictions WHERE pair_key = ?",
                        (pair_row["pair_key"],),
                    ).fetchone()["count"]
                    if reference_count == 0:
                        connection.execute(
                            "DELETE FROM contradictions WHERE pair_key = ?",
                            (pair_row["pair_key"],),
                        )

                for paper_row in paper_rows:
                    paper_id = paper_row["paper_id"]
                    job_count = connection.execute(
                        "SELECT COUNT(*) AS count FROM job_papers WHERE paper_id = ?",
                        (paper_id,),
                    ).fetchone()["count"]
                    search_count = connection.execute(
                        "SELECT COUNT(*) AS count FROM search_run_papers WHERE paper_id = ?",
                        (paper_id,),
                    ).fetchone()["count"]
                    if job_count == 0 and search_count == 0:
                        connection.execute(
                            "DELETE FROM claims WHERE paper_id = ?", (paper_id,)
                        )
                        connection.execute(
                            "DELETE FROM papers WHERE id = ?", (paper_id,)
                        )
                connection.commit()
        return True

    def get_job_stats(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        claim_tokens = job.extracted_claim_count * 300
        contradiction_tokens = job.scored_pair_count * 400
        eligible_pairs = int(
            job.metadata.get(
                "total_eligible_pairs", job.scored_pair_count + job.cached_pair_count
            )
            or 0
        )
        denominator = eligible_pairs if eligible_pairs > 0 else 1
        cache_hit_rate = (
            round(job.cached_pair_count / denominator, 4) if eligible_pairs else 0.0
        )
        return {
            "job_id": job.id,
            "query": job.query,
            "status": job.status.value,
            "paper_count": job.paper_count,
            "extracted_claim_count": job.extracted_claim_count,
            "skipped_claim_count": job.skipped_claim_count,
            "cluster_count": job.cluster_count,
            "filtered_pair_count": job.filtered_pair_count,
            "scored_pair_count": job.scored_pair_count,
            "contradiction_count": job.contradiction_count,
            "cache_hit_rate": cache_hit_rate,
            "duration_ms": job.duration_ms,
            "cost_estimate": {
                "claim_extraction_tokens": claim_tokens,
                "contradiction_scoring_tokens": contradiction_tokens,
                "total_tokens": claim_tokens + contradiction_tokens,
            },
            "metadata": job.metadata,
        }

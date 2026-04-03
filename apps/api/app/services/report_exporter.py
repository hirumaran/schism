from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Iterator

from app.models.report import AnalysisReport


class ReportExporter:
    @staticmethod
    def _claim_lookup(report: AnalysisReport) -> dict[str, str]:
        return {claim.paper_id: claim.claim or "" for claim in report.claims}

    @staticmethod
    def build_filename(query: str | None, extension: str) -> str:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        base = re.sub(r"[^a-z0-9]+", "_", (query or "report").lower()).strip("_") or "report"
        return f"schism_{base}_{date_part}.{extension}"

    def to_json_payload(self, report: AnalysisReport) -> dict[str, Any]:
        paper_lookup = {paper.id: paper for paper in report.papers}
        claim_lookup = self._claim_lookup(report)
        contradictions = []
        for rank, contradiction in enumerate(sorted(report.contradictions, key=lambda item: item.score, reverse=True), start=1):
            paper_a = paper_lookup.get(contradiction.paper_a_id)
            paper_b = paper_lookup.get(contradiction.paper_b_id)
            if paper_a is None or paper_b is None:
                continue
            contradictions.append(
                {
                    "rank": rank,
                    "score": contradiction.score,
                    "type": contradiction.type.value if contradiction.type else "",
                    "explanation": contradiction.explanation,
                    "key_difference": contradiction.key_difference,
                    "could_both_be_true": contradiction.could_both_be_true,
                    "paper_a": {
                        "title": paper_a.title,
                        "authors": paper_a.authors,
                        "year": paper_a.year,
                        "url": paper_a.url,
                        "claim": contradiction.paper_a_claim or claim_lookup.get(paper_a.id, ""),
                        "source": paper_a.source,
                    },
                    "paper_b": {
                        "title": paper_b.title,
                        "authors": paper_b.authors,
                        "year": paper_b.year,
                        "url": paper_b.url,
                        "claim": contradiction.paper_b_claim or claim_lookup.get(paper_b.id, ""),
                        "source": paper_b.source,
                    },
                }
            )
        return {
            "schism_version": "0.1.0",
            "query": report.query,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "paper_count": len(report.papers),
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
        }

    def to_json_text(self, report: AnalysisReport) -> str:
        return json.dumps(self.to_json_payload(report), indent=2)

    def to_csv(self, report: AnalysisReport) -> str:
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "rank",
                "score",
                "type",
                "explanation",
                "key_difference",
                "paper_a_title",
                "paper_a_year",
                "paper_a_url",
                "paper_a_claim",
                "paper_b_title",
                "paper_b_year",
                "paper_b_url",
                "paper_b_claim",
            ],
        )
        writer.writeheader()
        paper_lookup = {paper.id: paper for paper in report.papers}
        claim_lookup = self._claim_lookup(report)

        for rank, contradiction in enumerate(sorted(report.contradictions, key=lambda item: item.score, reverse=True), start=1):
            paper_a = paper_lookup.get(contradiction.paper_a_id)
            paper_b = paper_lookup.get(contradiction.paper_b_id)
            if paper_a is None or paper_b is None:
                continue
            writer.writerow(
                {
                    "rank": rank,
                    "score": contradiction.score,
                    "type": contradiction.type.value if contradiction.type else "",
                    "explanation": contradiction.explanation,
                    "key_difference": contradiction.key_difference or "",
                    "paper_a_title": paper_a.title,
                    "paper_a_year": paper_a.year or "",
                    "paper_a_url": paper_a.url or "",
                    "paper_a_claim": contradiction.paper_a_claim or claim_lookup.get(paper_a.id, ""),
                    "paper_b_title": paper_b.title,
                    "paper_b_year": paper_b.year or "",
                    "paper_b_url": paper_b.url or "",
                    "paper_b_claim": contradiction.paper_b_claim or claim_lookup.get(paper_b.id, ""),
                }
            )
        return output.getvalue()

    def iter_csv(self, report: AnalysisReport) -> Iterator[str]:
        yield self.to_csv(report)

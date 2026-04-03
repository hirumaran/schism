from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from app.models.report import AnalysisReport


class ReportExporter:
    @staticmethod
    def to_json_payload(report: AnalysisReport) -> dict[str, Any]:
        return report.model_dump(mode="json")

    @staticmethod
    def to_csv(report: AnalysisReport) -> str:
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "report_id",
                "paper_a_id",
                "paper_a_title",
                "paper_b_id",
                "paper_b_title",
                "cluster_id",
                "score",
                "type",
                "is_contradiction",
                "explanation",
            ],
        )
        writer.writeheader()
        paper_lookup = {paper.id: paper for paper in report.papers}

        for contradiction in report.contradictions:
            writer.writerow(
                {
                    "report_id": report.id,
                    "paper_a_id": contradiction.paper_a_id,
                    "paper_a_title": paper_lookup.get(contradiction.paper_a_id).title
                    if contradiction.paper_a_id in paper_lookup
                    else "",
                    "paper_b_id": contradiction.paper_b_id,
                    "paper_b_title": paper_lookup.get(contradiction.paper_b_id).title
                    if contradiction.paper_b_id in paper_lookup
                    else "",
                    "cluster_id": contradiction.cluster_id or "",
                    "score": contradiction.score,
                    "type": contradiction.type.value if contradiction.type else "",
                    "is_contradiction": contradiction.is_contradiction,
                    "explanation": contradiction.explanation,
                }
            )

        return output.getvalue()

    @staticmethod
    def to_json_text(report: AnalysisReport) -> str:
        return json.dumps(report.model_dump(mode="json"), indent=2)


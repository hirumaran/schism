from __future__ import annotations

from io import BytesIO
import re

from fastapi import UploadFile
from pydantic import BaseModel

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional at import time for tests
    PdfReader = None


from app.services.summarizer import DocumentCompressor


SECTION_HEADINGS = {
    "abstract",
    "summary",
    "introduction",
    "background",
    "methods",
    "materials and methods",
    "results",
    "discussion",
    "conclusion",
    "conclusions",
    "references",
}
ABSTRACT_HEADINGS = {"abstract", "summary"}
CONCLUSION_HEADINGS = {"conclusion", "conclusions", "discussion"}


class ParsedInput(BaseModel):
    text: str
    title: str | None = None
    filename: str | None = None


class ExtractedSections(BaseModel):
    abstract: str | None = None
    conclusion: str | None = None
    full_text: str
    compressed_text: str | None = None
    best_section: str


class PaperInputParser:
    async def parse_upload(
        self, file: UploadFile, title: str | None = None
    ) -> ParsedInput:
        filename = file.filename or "upload"
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        payload = await file.read()
        resolved_title = (title or "").strip() or None
        if suffix == "pdf":
            if PdfReader is None:
                raise ValueError(
                    "PDF parsing is unavailable because pypdf is not installed."
                )
            reader = PdfReader(BytesIO(payload))
            text = "\n".join(
                (page.extract_text() or "") for page in reader.pages
            ).strip()
            if len(text) < 200:
                raise ValueError(
                    "PDF text extraction failed - try pasting text directly"
                )
            return ParsedInput(text=text, title=resolved_title, filename=filename)
        if suffix in {"txt", "md"}:
            return ParsedInput(
                text=payload.decode("utf-8").strip(),
                title=resolved_title,
                filename=filename,
            )
        raise ValueError("Unsupported upload type. Use PDF, TXT, or MD.")

    async def parse_text(self, text: str, title: str | None) -> ParsedInput:
        stripped = (text or "").strip()
        if len(stripped) < 100:
            raise ValueError("Input text must be at least 100 characters long.")
        resolved_title = (title or "").strip() or None
        return ParsedInput(text=stripped, title=resolved_title)

    def extract_sections(self, text: str) -> ExtractedSections:
        from app.config import get_settings

        settings = get_settings()

        normalized = self._normalize_text(text)
        lines = normalized.split("\n")
        abstract = self._extract_section(lines, ABSTRACT_HEADINGS)
        conclusion = self._extract_section(lines, CONCLUSION_HEADINGS)

        compressor = DocumentCompressor(
            algorithm=settings.summarization_algorithm, ratio=settings.compression_ratio
        )
        body_parts = []
        if abstract:
            body_parts.append(f"Abstract:\n{abstract}")

        # For simplicity, if we compress the whole text (it drops math and handles length logic)
        # We can extract the compressed text.
        compressed = compressor.compress(normalized)
        if compressed and compressed != normalized:
            if not abstract and not conclusion:
                compressed_text = compressed
            else:
                body_parts.append(f"Body:\n{compressed}")
                if conclusion:
                    body_parts.append(f"Conclusion:\n{conclusion}")
                compressed_text = "\n\n".join(body_parts)
        else:
            compressed_text = normalized

        best_section = abstract or conclusion or compressed_text[:3000]

        return ExtractedSections(
            abstract=abstract,
            conclusion=conclusion,
            full_text=normalized,
            compressed_text=compressed_text,
            best_section=best_section,
        )

    def _extract_section(
        self, lines: list[str], target_headings: set[str]
    ) -> str | None:
        for index, line in enumerate(lines):
            normalized = self._normalize_heading(line)
            if normalized not in target_headings:
                continue
            body: list[str] = []
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if not stripped:
                    if body:
                        body.append("")
                    continue
                if self._normalize_heading(stripped) in SECTION_HEADINGS:
                    break
                body.append(stripped)
            section = "\n".join(part for part in body if part is not None).strip()
            if section:
                return section
        return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(
            r"\n{3,}", "\n\n", (text or "").replace("\r\n", "\n").replace("\r", "\n")
        ).strip()

    @staticmethod
    def _normalize_heading(line: str) -> str:
        cleaned = re.sub(r"^[0-9.\s]+", "", (line or "").strip().lower()).rstrip(":")
        if len(cleaned) > 80:
            return ""
        return cleaned

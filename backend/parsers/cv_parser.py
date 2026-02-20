"""
CV Parser  (Perplexity sonar)
==============================
Uses the cheapest Perplexity model (sonar $1/$1) for CV text extraction.
No web search needed here — just structured JSON extraction from text.
"""

import json
import tempfile
from pathlib import Path
from typing import Union

from ..ai_client import chat_single, SONAR


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file."""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        pass
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error extracting PDF: {e}"


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes (e.g. from file upload)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    text = extract_text_from_pdf(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
    return text


def parse_cv_with_ai(cv_text: str) -> dict:
    """Use Perplexity sonar to extract structured data from CV text."""

    prompt = f"""Parse this CV and return ONLY a JSON object. No explanations, no markdown — raw JSON only.

CV TEXT:
{cv_text}

Return this exact JSON structure:
{{
    "name": "full name",
    "email": "email@example.com",
    "phone": "+351 xxx xxx xxx",
    "location": "City, Country",
    "current_title": "Software Developer",
    "target_title": "Senior Backend Developer",
    "years_experience": 3,
    "summary": "2-3 sentence professional summary",
    "skills": [
        {{"name": "Python", "level": "intermediate", "years": 2, "category": "programming"}}
    ],
    "education": [
        {{"degree": "BSc Computer Science", "institution": "University of Porto", "year": 2021, "field": "Computer Science"}}
    ],
    "experience": [
        {{
            "title": "Junior Developer",
            "company": "Tech Co",
            "duration_months": 24,
            "technologies": ["Python", "Django"],
            "highlights": ["Built REST API serving 10k users"]
        }}
    ],
    "languages": [
        {{"language": "Portuguese", "level": "native"}},
        {{"language": "English", "level": "B2"}}
    ],
    "certifications": []
}}"""

    response_text = chat_single(
        prompt=prompt,
        model=SONAR,          # cheapest model — no web search needed
        max_tokens=4096,
        temperature=0.1,      # low temp for deterministic JSON
    )

    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(response_text[start:end])
        except json.JSONDecodeError:
            pass

    return {"raw_text": cv_text, "parse_error": "Could not parse JSON from response"}


def parse_cv(input_data: Union[str, bytes], input_type: str = "text") -> dict:
    """
    Main entry point for CV parsing.

    Args:
        input_data: CV content (text string, PDF path, or PDF bytes)
        input_type: "text" | "pdf_path" | "pdf_bytes"
    """
    if input_type == "pdf_path":
        cv_text = extract_text_from_pdf(str(input_data))
    elif input_type == "pdf_bytes":
        cv_text = extract_text_from_bytes(input_data)
    else:
        cv_text = str(input_data)

    if not cv_text or len(cv_text.strip()) < 50:
        return {"error": "Could not extract meaningful text from CV"}

    return parse_cv_with_ai(cv_text)

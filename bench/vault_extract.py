"""
vault_extract.py — RoutingNeedle vault corpus adapter
Replaces CodeNeedle's extract.py for Obsidian Markdown documents.

CORPUS CONSTRAINT: .md files only.
Non-.md inputs are hard-rejected with an explicit error.
Silent skips are not permitted.
"""

import pathlib
import re
from dataclasses import dataclass
from typing import List


@dataclass
class ClaimTarget:
    """A named extractable claim from a vault document."""
    name: str          # Human-readable claim label
    expected: str      # Expected extraction value (exact)
    position: float    # Relative position in document (0.0–1.0)
    field_type: str    # "table_cell", "frontmatter", "list_item", "inline"
    section: str       # Section heading context


def _assert_md_only(path: pathlib.Path) -> None:
    """Hard reject non-.md files. Not a silent skip."""
    if path.suffix.lower() != ".md":
        raise ValueError(
            f"RoutingNeedle corpus constraint violation: "
            f"only .md files are permitted. "
            f"Received: {path} (suffix: {path.suffix}). "
            f"Non-Markdown files are excluded from all RoutingNeedle runs."
        )


def load_vault_document(path: str | pathlib.Path) -> str:
    """Load an Obsidian Markdown document. Raises on non-.md input."""
    p = pathlib.Path(path)
    _assert_md_only(p)
    return p.read_text(encoding="utf-8")


def load_corpus_glob(pattern: str, base: str | pathlib.Path) -> List[pathlib.Path]:
    """
    Glob for corpus files. Returns only .md files.
    Raises ValueError if any non-.md file is found in the glob results.
    """
    base_path = pathlib.Path(base)
    all_files = list(base_path.glob(pattern))
    non_md = [f for f in all_files if f.suffix.lower() != ".md"]
    if non_md:
        raise ValueError(
            f"RoutingNeedle corpus constraint violation: "
            f"non-.md files found in glob '{pattern}': "
            f"{[str(f) for f in non_md]}. "
            f"Restrict glob to '**/*.md'."
        )
    return [f for f in all_files if f.suffix.lower() == ".md"]


def extract_frontmatter_fields(content: str) -> dict:
    """Extract YAML frontmatter key-value pairs."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def extract_table_cells(content: str, section_hint: str = "") -> List[ClaimTarget]:
    """
    Extract named cells from Markdown tables.
    Returns ClaimTarget list with position and section context.
    """
    targets = []
    lines = content.split("\n")
    total = len(lines)
    current_section = ""

    for i, line in enumerate(lines):
        if line.startswith("#"):
            current_section = line.lstrip("#").strip()
        if section_hint and section_hint.lower() not in current_section.lower():
            continue
        if "|" in line and not line.strip().startswith("|---"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                targets.append(ClaimTarget(
                    name=cells[0],
                    expected=cells[1] if len(cells) > 1 else "",
                    position=round(i / total, 3),
                    field_type="table_cell",
                    section=current_section,
                ))
    return targets

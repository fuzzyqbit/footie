"""Generic markdown pipe-table extraction."""

from __future__ import annotations


def _clean_cell(cell: str) -> str:
    return cell.replace("**", "").replace("★", "").strip()


def _is_separator(cells: list[str]) -> bool:
    return all(cell and set(cell) <= set(":- ") for cell in cells)


def extract_tables(markdown: str) -> list[list[dict[str, str]]]:
    """Return each pipe table as a list of {header: cell} row dicts."""
    tables: list[list[dict[str, str]]] = []
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None and rows:
                tables.append(rows)
            header, rows = None, []
            continue
        cells = [_clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if header is None:
            header = cells
        elif _is_separator(cells):
            continue
        else:
            # pad short rows so every header key exists; extra cells beyond
            # the header are dropped (standard pipe-table semantics)
            padded = cells + [""] * (len(header) - len(cells))
            rows.append(dict(zip(header, padded)))
    if header is not None and rows:
        tables.append(rows)
    return tables

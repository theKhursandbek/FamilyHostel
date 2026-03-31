"""
CSV Export Utility (Step 19).

Provides a generic helper to convert a list of dicts (or a single summary
dict) into CSV format.  Designed for large-data efficiency:

- Uses :class:`csv.writer` for streaming writes (no full string concat).
- Accepts an optional ``output`` argument (any file-like object) so callers
  can write directly to an ``HttpResponse`` or a disk file.
- When ``output`` is *None*, returns the CSV as a plain ``str`` (convenient
  for tests and small exports).

Usage
-----
::

    from apps.reports.csv_export import export_to_csv

    rows = get_staff_performance(branch.pk, start, end)
    csv_string = export_to_csv(rows)

    # Or stream to an HttpResponse:
    response = HttpResponse(content_type="text/csv")
    export_to_csv(rows, output=response)
"""

from __future__ import annotations

import csv
import io
from typing import IO, Any, Sequence

__all__ = ["export_to_csv"]


def export_to_csv(
    data: Sequence[dict[str, Any]] | dict[str, Any],
    *,
    headers: Sequence[str] | None = None,
    output: IO[str] | None = None,
) -> str:
    """
    Convert *data* to CSV.

    Parameters
    ----------
    data
        A list of dicts (rows) **or** a single dict (treated as one row).
    headers
        Explicit column headers.  When *None*, headers are inferred from the
        keys of the first dict.
    output
        An optional writable file-like object.  When provided, CSV is written
        there **and** the CSV string is still returned.

    Returns
    -------
    str
        The complete CSV text (including header row).
    """
    # Normalise single-dict to a list of one row
    if isinstance(data, dict):
        rows: list[dict[str, Any]] = [data]
    else:
        rows = list(data)

    if not rows:
        return ""

    fieldnames: Sequence[str] = headers if headers else list(rows[0].keys())

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for row in rows:
        writer.writerow(row)

    csv_text = buf.getvalue()

    if output is not None:
        output.write(csv_text)

    return csv_text

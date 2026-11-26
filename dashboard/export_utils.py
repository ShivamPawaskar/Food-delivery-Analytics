"""Pure export helpers, separated from Streamlit widgets for testing."""
from __future__ import annotations

from io import BytesIO
import zipfile

import pandas as pd


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def csv_zip_bytes(reports: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, frame in reports.items():
            archive.writestr(f"{name}.csv", csv_bytes(frame))
    return buffer.getvalue()

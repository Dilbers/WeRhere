from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


DRIVE_WORKBOOK_URLS = {
    "Applications": "https://docs.google.com/spreadsheets/d/1djywK6nYfRnn0Al9en31ozECUkhwUwsD/export?format=xlsx",
    "Interviews": "https://docs.google.com/spreadsheets/d/1EzQvehWRgMb0Yfv3DayW5bRcqGfq_zGx/export?format=xlsx",
    "Mentor": "https://docs.google.com/spreadsheets/d/10xwqwTKYPau3Lo91UmGLKCga8gXBTdaR/export?format=xlsx",
    "Users": "https://docs.google.com/spreadsheets/d/1FlLWRXx2rI42g87Wm87WnRE_c-e_p-Oh/export?format=xlsx",
}

REQUIRED_SHEETS = {
    "Applications": {
        "Applications": {"Full Name", "Desired Training", "Province", "Current Status", "Processing Status", "Timestamp"},
    },
    "Interviews": {
        "Interviews": {"Full Name", "Project Sent Date", "Project Received Date"},
    },
    "Mentor": {
        "Mentor": {"Date", "Candidate Name", "Mentor Name"},
        "Mentor Recommendation Options": {"Recommendation Option (English)"},
    },
    "Users": {
        "Users": {"Username", "Password", "Role"},
    },
}

MAX_WORKBOOK_BYTES = 20 * 1024 * 1024


class DriveImportError(RuntimeError):
    """Raised when the shared source data cannot be downloaded or validated."""


def download_workbooks() -> dict[str, bytes]:
    workbooks: dict[str, bytes] = {}
    for name, url in DRIVE_WORKBOOK_URLS.items():
        request = Request(url, headers={"User-Agent": "WeRhere desktop app"})
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read(MAX_WORKBOOK_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise DriveImportError(
                f"Could not download {name}.xlsx from the shared Google Drive folder."
            ) from error
        if len(content) > MAX_WORKBOOK_BYTES:
            raise DriveImportError(f"{name}.xlsx exceeds the 20 MB import limit.")
        workbooks[name] = content
    return workbooks


def read_workbooks(
    workbook_sources: Mapping[str, bytes],
) -> dict[str, list[dict[str, Any]]]:
    if set(workbook_sources) != set(REQUIRED_SHEETS):
        raise DriveImportError(
            "The shared folder must contain Applications.xlsx, Interviews.xlsx, "
            "Mentor.xlsx, and Users.xlsx."
        )

    parsed: dict[str, list[dict[str, Any]]] = {}
    for workbook_name, required_sheets in REQUIRED_SHEETS.items():
        try:
            workbook = load_workbook(
                BytesIO(workbook_sources[workbook_name]),
                read_only=True,
                data_only=False,
            )
        except (BadZipFile, InvalidFileException, OSError, ValueError) as error:
            raise DriveImportError(
                f"{workbook_name}.xlsx is not a readable Excel workbook."
            ) from error

        try:
            if not set(required_sheets).issubset(workbook.sheetnames):
                raise DriveImportError(
                    f"{workbook_name}.xlsx is missing a required worksheet."
                )
            sheets = []
            for sheet_name, required_headers in required_sheets.items():
                sheet = workbook[sheet_name]
                iterator = sheet.iter_rows(values_only=True)
                first_row = next(iterator, None)
                if first_row is None:
                    raise DriveImportError(
                        f"{workbook_name}.xlsx has an empty {sheet_name} worksheet."
                    )
                headers = [
                    str(value).strip() if value is not None else ""
                    for value in first_row
                ]
                if any(headers.count(header) != 1 for header in required_headers):
                    raise DriveImportError(
                        f"{workbook_name}.xlsx has an unexpected {sheet_name} header row."
                    )
                rows = [
                    (row_number, list(row))
                    for row_number, row in enumerate(iterator, start=2)
                    if any(value is not None for value in row)
                ]
                sheets.append(
                    {
                        "sheet_name": sheet_name,
                        "headers": headers,
                        "rows": rows,
                    }
                )
            parsed[workbook_name] = sheets
        finally:
            workbook.close()
    return parsed

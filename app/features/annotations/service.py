import re
from typing import List

from fastapi import HTTPException


def parse_page_range(raw: str | None) -> tuple[int, int] | None:
    if raw is None:
        return None

    value = raw.strip()
    if not value:
        return None

    single = re.fullmatch(r"(\d+)", value)
    if single:
        page = int(single.group(1))
        if page < 1:
            raise HTTPException(status_code=422, detail="pageRange must start at page 1")
        page_idx = page - 1
        return page_idx, page_idx

    span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", value)
    if not span:
        raise HTTPException(status_code=422, detail="pageRange must be like '3' or '3-7'")

    start_page = int(span.group(1))
    end_page = int(span.group(2))
    if start_page < 1 or end_page < 1:
        raise HTTPException(status_code=422, detail="pageRange must start at page 1")
    if end_page < start_page:
        raise HTTPException(status_code=422, detail="pageRange end must be >= start")

    return start_page - 1, end_page - 1


def normalize_rects(rects: list[tuple[float, float, float, float] | None]) -> List[List[float]]:
    out: List[List[float]] = []
    for r in rects:
        if r is None:
            continue
        out.append([float(x) for x in r])
    return out

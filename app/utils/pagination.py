from dataclasses import dataclass


@dataclass
class PaginationMeta:
    page: int
    limit: int
    total: int
    offset: int


def build_pagination(page: int, limit: int) -> PaginationMeta:
    """
    Compute offset from page + limit.
    All callers use this so pagination logic is never duplicated.
    """
    page = max(1, page)
    limit = min(max(1, limit), 50)
    offset = (page - 1) * limit
    return PaginationMeta(page=page, limit=limit, total=0, offset=offset)

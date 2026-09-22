from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination_params(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int

from sqlalchemy import column, func, select
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from src.api.schemas.garden import GardenSearchFacets, GardenSearchFilter
from src.models.base import Base


def apply_filters(
    model: Base, stmt: Select, filters: list[GardenSearchFilter]
) -> Select:
    """
    Construct a new SQLAlchemy `Select` statement with applied filters.

    This function takes an existing SQLAlchemy `Select` statement and applies additional
    `WHERE` clauses based on the provided `filters`. Each filter in the `filters` list is
    ANDed together, meaning that all conditions must be satisfied for a row to be included
    in the result.

    Args:
        model (Base): The SQLAlchemy model to which the filters should be applied.
                      This should be a class derived from `src.models.base.Base`.
        stmt (Select): The initial SQLAlchemy `Select` statement to be modified.
        filters (list[GardenSearchFilter]): A list of `GardenSearchFilter` instances, where each filter
                                            specifies a `field_name` and a list of `values` to match.

    Returns:
        Select: A new `Select` statement with the additional `WHERE` clauses based on the provided filters.

    Raises:
        ValueError: If a `field_name` in a filter does not correspond to an attribute on the `model`.

    Example:
        Given a model `Garden` with attributes `title`, `description`, and `tags`:

        ```
        filters = [
            GardenSearchFilter(field_name="title", values=["flower"]),
            GardenSearchFilter(field_name="tags", values=["botany"])
        ]
        query = select(Garden)
        query_with_filters = apply_filters(Garden, query, filters)
        ```

        This will generate a query with `WHERE` clauses matching the title and tags.
    """
    for filter in filters:
        if not hasattr(model, filter.field_name):
            raise ValueError(f"Invalid filter field_name: {filter.field_name}")
        for value in filter.values:
            if type(getattr(model, filter.field_name).type) is ARRAY:
                stmt = stmt.where(
                    func.array_to_string(getattr(model, filter.field_name), " ").match(
                        value
                    )
                )
            else:
                stmt = stmt.where(
                    func.cast(getattr(model, filter.field_name), TEXT).match(value)
                )
    return stmt


async def calculate_facets(db: AsyncSession, query: Select) -> GardenSearchFacets:
    """Calculate and return search facets for a given query.

    This function computes facet counts for tags, authors, and years based on the
    result set from the provided SQLAlchemy Select statement. Facets are calculated
    by grouping on specific fields (`tags`, `authors`, and `year`) and counting
    occurrences within the subset of gardens returned by the query.

    Args:
        db (AsyncSession): The asynchronous SQLAlchemy session used to execute queries.
        query (Select): A SQLAlchemy `Select` statement representing the filtered subset
                        of gardens to calculate facets from.

    Returns:
        GardenSearchFacets: An instance of `GardenSearchFacets` containing three fields:
            - `tags` (dict[str, int]): A dictionary where keys are individual tags and values
              are the count of gardens associated with each tag.
            - `authors` (dict[str, int]): A dictionary where keys are author names and values
              are the count of gardens authored by each individual.
            - `year` (dict[str, int]): A dictionary where keys are years (as strings) and values
              are the count of gardens created in each year.

    Note:
        This function assumes that the query provided returns results from a table or view that
        includes the columns `tags`, `authors`, and `year` as arrays or individual fields.
    """
    filtered_gardens = query.subquery("filtered_gardens")

    tags_query = select(
        func.unnest(filtered_gardens.c.tags).label("tag"), func.count().label("count")
    ).group_by(column("tag"))

    authors_query = select(
        func.unnest(filtered_gardens.c.authors).label("author"),
        func.count().label("count"),
    ).group_by(column("author"))

    year_query = select(
        filtered_gardens.c.year.label("year"), func.count().label("count")
    ).group_by(column("year"))

    tags_result = await db.execute(tags_query)
    authors_result = await db.execute(authors_query)
    year_result = await db.execute(year_query)

    tags = {row[0]: row[1] for row in tags_result.all()}
    authors = {row[0]: row[1] for row in authors_result.all()}
    year = {str(row[0]): row[1] for row in year_result.all()}

    return GardenSearchFacets(tags=tags, authors=authors, year=year)

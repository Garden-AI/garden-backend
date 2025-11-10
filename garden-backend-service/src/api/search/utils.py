from sqlalchemy import asc, column, desc, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from src.api.schemas.garden import (
    GardenSearchFacets,
    GardenSearchFilter,
    GardenSearchSort,
)
from src.models import User
from src.models._associations import (
    gardens_hpc_functions,
    gardens_modal_functions,
    hpc_functions_hpc_endpoints,
)
from src.models.base import Base
from src.models.functions.hpc.hpc_endpoints import HpcEndpoint


def apply_function_type_filter(
    model: type[Base],
    stmt: Select,
    values: list[str],
) -> Select:
    """
    Filter gardens by function type (modal, hpc, or both).

    Args:
        model: The Garden model
        stmt: The SQLAlchemy Select statement
        values: List of function types - ["modal"], ["hpc"], or ["modal", "hpc"]

    Returns:
        Modified Select statement with function type filter applied
    """
    if not values:
        return stmt

    function_type_conditions = []

    for value in values:
        if value == "modal":
            # Garden has at least one modal function
            function_type_conditions.append(getattr(model, "modal_functions").any())
        elif value == "hpc":
            # Garden has at least one HPC function
            function_type_conditions.append(getattr(model, "hpc_functions").any())

    # Apply OR logic: garden must have at least one of the requested function types
    if function_type_conditions:
        stmt = stmt.where(or_(*function_type_conditions))

    return stmt


def apply_hpc_endpoints_filter(
    model: type[Base], stmt: Select, endpoint_names: list[str]
) -> Select:
    """
    Filter gardens that have HPC functions available on specific endpoints.

    Args:
        model: The Garden model
        stmt: The SQLAlchemy Select statement
        endpoint_names: List of HPC endpoint names (e.g., ["Polaris", "Perlmutter"])

    Returns:
        Modified Select statement with HPC endpoint filter applied
    """
    if not endpoint_names:
        return stmt

    # Filter to gardens where ANY HPC function has ANY of the specified endpoints
    subquery = (
        select(gardens_hpc_functions.c.garden_id)
        .join(
            hpc_functions_hpc_endpoints,
            gardens_hpc_functions.c.hpc_function_id
            == hpc_functions_hpc_endpoints.c.hpc_function_id,
        )
        .join(
            HpcEndpoint,
            hpc_functions_hpc_endpoints.c.hpc_endpoint_id == HpcEndpoint.id,
        )
        .where(HpcEndpoint.name.in_(endpoint_names))
    )

    stmt = stmt.where(getattr(model, "id").in_(subquery))

    return stmt


def apply_filters(
    model: type[Base], stmt: Select, filters: list[GardenSearchFilter]
) -> Select:
    """
    Construct a new SQLAlchemy `Select` statement with applied filters.

    This function takes an existing SQLAlchemy `Select` statement and applies additional
    `WHERE` clauses based on the provided `filters`.

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
        if filter.field_name == "function_type":
            stmt = apply_function_type_filter(model, stmt, filter.values)
            continue

        if filter.field_name == "hpc_endpoints":
            stmt = apply_hpc_endpoints_filter(model, stmt, filter.values)
            continue

        # Validate that the field exists on the model for standard filters
        if not hasattr(model, filter.field_name):
            raise ValueError(f"Invalid filter field_name: {filter.field_name}")

        or_conditions = []
        for value in filter.values:
            if filter.field_name == "owner":
                if filter.operation == "OR":
                    or_conditions.append(User.name == value)
                else:
                    stmt = stmt.join(getattr(model, filter.field_name)).where(
                        User.name == value
                    )
            elif type(getattr(model, filter.field_name)) is ARRAY:
                if filter.operation == "OR":
                    or_conditions.append(
                        func.array_to_string(
                            getattr(model, filter.field_name), " "
                        ).match(value)
                    )
                else:
                    stmt = stmt.where(
                        func.array_to_string(
                            getattr(model, filter.field_name), " "
                        ).match(value)
                    )
            elif filter.field_name == "doi":
                if filter.operation == "OR":
                    or_conditions.append(getattr(model, filter.field_name) == value)
                else:
                    stmt = stmt.where(getattr(model, filter.field_name) == value)
            else:
                if filter.operation == "OR":
                    or_conditions.append(
                        func.cast(getattr(model, filter.field_name), TEXT).match(value)
                    )
                else:
                    stmt = stmt.where(
                        func.cast(getattr(model, filter.field_name), TEXT).match(value)
                    )
        if or_conditions:
            stmt = stmt.where(or_(*or_conditions))
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
            - `gardeners` (dict[str, int]): A dictionary where keys are gardner names and values
              are the count of gardens created by each gardener.
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
        func.unnest(filtered_gardens.c.authors).label("model_author"),
        func.count().label("count"),
    ).group_by(column("model_author"))

    gardeners_query = (
        select(
            User.name.label("gardener"),
            func.count().label(name="count"),
        )
        .join(filtered_gardens, User.id == filtered_gardens.c.user_id)
        .group_by(column("gardener"))
    )

    year_query = select(
        filtered_gardens.c.year.label("year"), func.count().label("count")
    ).group_by(column("year"))

    # Function types facet: count gardens by whether they have modal/hpc functions
    # Use UNION to get counts for both types
    modal_count_query = (
        select(
            literal_column("'modal'").label("function_type"),
            func.count().label("count"),
        )
        .select_from(filtered_gardens)
        .where(
            select(1)
            .select_from(gardens_modal_functions)
            .where(gardens_modal_functions.c.garden_id == filtered_gardens.c.id)
            .exists()
        )
    )

    hpc_count_query = (
        select(
            literal_column("'hpc'").label("function_type"), func.count().label("count")
        )
        .select_from(filtered_gardens)
        .where(
            select(1)
            .select_from(gardens_hpc_functions)
            .where(gardens_hpc_functions.c.garden_id == filtered_gardens.c.id)
            .exists()
        )
    )

    function_types_query = modal_count_query.union_all(hpc_count_query)

    # HPC endpoints facet: count unique endpoint names across all HPC functions
    hpc_endpoints_query = (
        select(HpcEndpoint.name.label("endpoint"), func.count().label("count"))
        .select_from(filtered_gardens)
        .join(
            gardens_hpc_functions,
            filtered_gardens.c.id == gardens_hpc_functions.c.garden_id,
        )
        .join(
            hpc_functions_hpc_endpoints,
            gardens_hpc_functions.c.hpc_function_id
            == hpc_functions_hpc_endpoints.c.hpc_function_id,
        )
        .join(
            HpcEndpoint,
            hpc_functions_hpc_endpoints.c.hpc_endpoint_id == HpcEndpoint.id,
        )
        .group_by(HpcEndpoint.name)
    )

    tags_result = await db.execute(tags_query)
    authors_result = await db.execute(authors_query)
    gardeners_result = await db.execute(gardeners_query)
    year_result = await db.execute(year_query)
    function_types_result = await db.execute(function_types_query)
    hpc_endpoints_result = await db.execute(hpc_endpoints_query)

    tags = {row[0]: row[1] for row in tags_result.all()}
    authors = {row[0]: row[1] for row in authors_result.all()}
    gardeners = {row[0]: row[1] for row in gardeners_result.all()}
    year = {str(row[0]): row[1] for row in year_result.all()}
    function_types = {row[0]: row[1] for row in function_types_result.all()}
    hpc_endpoints = {row[0]: row[1] for row in hpc_endpoints_result.all()}

    return GardenSearchFacets(
        tags=tags,
        model_authors=authors,
        gardeners=gardeners,
        year=year,
        function_type=function_types,
        hpc_endpoint=hpc_endpoints,
    )


def sort_results(model: Base, stmt: Select, sort: GardenSearchSort):
    if not hasattr(model, sort.field_name):
        raise ValueError(f"Invalid sort field_name: {sort.field_name}")

    match sort.order:
        case "asc":
            return stmt.order_by(asc(getattr(model, sort.field_name)))
        case "desc":
            return stmt.order_by(desc(getattr(model, sort.field_name)))
        case _:
            raise ValueError(
                f"Invalid sort order: {sort.order}. Must be 'asc' or 'desc'"
            )

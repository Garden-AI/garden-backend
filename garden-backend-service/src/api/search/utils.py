from sqlalchemy import column, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.garden import Facets


def apply_filters(cls, stmt, filters):
    for filter in filters:
        if not hasattr(cls, filter.field_name):
            raise ValueError(f"Invalid filter field_name: {filter.field_name}")
        for value in filter.values:
            if type(getattr(cls, filter.field_name).type) is ARRAY:
                stmt = stmt.where(
                    func.array_to_string(getattr(cls, filter.field_name), " ").match(
                        value
                    )
                )
            else:
                stmt = stmt.where(
                    func.cast(getattr(cls, filter.field_name), TEXT).match(value)
                )
    return stmt


async def register_search_function(session):
    search_function_sql = """
    -- Do a ranked full-text search on gardens and entrypoints
    -- Gardens are ranked by their relevance to the search plus their associated entrypoint's relevance to the search
    CREATE OR REPLACE FUNCTION search_gardens(search_query TEXT)
    RETURNS TABLE (garden_id int, rank real) AS $$
    DECLARE
        query tsquery := websearch_to_tsquery(search_query);
    BEGIN
        RETURN QUERY
        WITH entrypoints_weighted_documents AS (
            SELECT id,
            setweight(to_tsvector(array_to_string(e.authors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(e.tags, ' ')), 'B') ||
            setweight(to_tsvector(e.title), 'D') ||
            setweight(to_tsvector(e.description), 'D') AS ep_document
            FROM entrypoints e
        ), gardens_weighted_documents AS (
            SELECT g.id AS garden_id,
            setweight(to_tsvector(array_to_string(g.authors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(g.contributors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(g.tags, ' ')), 'B') ||
            setweight(to_tsvector(g.description), 'D') ||
            setweight(to_tsvector(g.title), 'D') AS garden_document
            FROM gardens g
        ), garden_entrypoint_ranks AS (
            SELECT gwd.garden_id,
                   ts_rank(gwd.garden_document, query) AS garden_rank,
                   SUM(ts_rank(ep.ep_document, query)) AS total_entrypoint_rank
            FROM gardens_weighted_documents gwd
            LEFT JOIN gardens_entrypoints ge ON gwd.garden_id = ge.garden_id
            LEFT JOIN entrypoints_weighted_documents ep ON ep.id = ge.entrypoint_id
            GROUP BY gwd.garden_id, gwd.garden_document
        )
        SELECT ger.garden_id, ger.garden_rank + COALESCE(ger.total_entrypoint_rank, 0) AS rank
        FROM garden_entrypoint_ranks ger
        WHERE garden_rank > 0 OR COALESCE(total_entrypoint_rank, 0) > 0
        ORDER BY rank DESC;
    END;
    $$ LANGUAGE plpgsql;
    """

    await session.execute(text(search_function_sql))
    await session.commit()


async def calculate_facets(db: AsyncSession, query) -> Facets:
    filtered_gardens = query.cte("filtered_gardens")

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

    return Facets(tags=tags, authors=authors, year=year)

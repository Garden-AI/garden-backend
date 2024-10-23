CREATE OR REPLACE FUNCTION search_gardens(search_query text)
RETURNS TABLE(garden_id int, rank real)
AS
    $$
DECLARE
    query tsquery := websearch_to_tsquery(search_query);
BEGIN
    RETURN QUERY
    WITH ep_ranks AS (
         SELECT ge.garden_id,
                COALESCE(SUM(ts_rank(ed.ep_document, query)), 0) AS rank
         FROM gardens_entrypoints ge
         INNER JOIN entrypoint_documents ed
         ON ge.entrypoint_id = ed.id
         GROUP BY ge.garden_id
    ), modal_function_ranks AS (
         SELECT gm.garden_id,
                COALESCE(SUM(ts_rank(mf.mf_document, query)), 0) AS rank
         FROM gardens_modal_functions gm
         INNER JOIN modal_function_documents mf
         ON gm.modal_function_id = mf.id
         GROUP BY gm.garden_id
    ), garden_ranks AS (
       SELECT gd.garden_id,
              COALESCE(ts_rank(gd.garden_document, query), 0)
              + COALESCE(ep_ranks.rank, 0)
              + COALESCE(mf_ranks.rank, 0) AS rank
       FROM garden_documents gd
       LEFT JOIN ep_ranks
       ON ep_ranks.garden_id = gd.garden_id
       LEFT JOIN modal_function_ranks mf_ranks
       ON mf_ranks.garden_id = gd.garden_id
    )
    SELECT gr.garden_id, gr.rank
    FROM garden_ranks gr
    WHERE gr.rank > 0
    ORDER BY gr.rank DESC;
END;
$$
language plpgsql
;


CREATE MATERIALIZED VIEW IF NOT EXISTS garden_documents AS
    SELECT g.id AS garden_id,
    setweight(to_tsvector(array_to_string(g.authors, ' ')), 'A') ||
    setweight(to_tsvector(array_to_string(g.contributors, ' ')), 'A') ||
    setweight(to_tsvector(array_to_string(g.tags, ' ')), 'B') ||
    setweight(to_tsvector(g.description), 'D') ||
    setweight(to_tsvector(g.title), 'D') AS garden_document
    FROM gardens g;


CREATE MATERIALIZED VIEW IF NOT EXISTS entrypoint_documents AS
    SELECT e.id,
    setweight(to_tsvector(array_to_string(e.authors, ' ')), 'A') ||
    setweight(to_tsvector(array_to_string(e.tags, ' ')), 'B') ||
    setweight(to_tsvector(e.title), 'D') ||
    setweight(to_tsvector(e.description), 'D') AS ep_document
    FROM entrypoints e;


CREATE MATERIALIZED VIEW IF NOT EXISTS modal_function_documents AS
    SELECT mf.id,
    setweight(to_tsvector(array_to_string(mf.authors, ' ')), 'A') ||
    setweight(to_tsvector(array_to_string(mf.tags, ' ')), 'A') ||
    setweight(to_tsvector(mf.title), 'D') ||
    setweight(to_tsvector(mf.description), 'D') AS mf_document
    FROM modal_functions mf;


CREATE INDEX IF NOT EXISTS garden_documents_index ON garden_documents USING GIN(garden_document);
CREATE INDEX IF NOT EXISTS entrypoint_documents_index ON entrypoint_documents USING GIN(ep_document);
CREATE INDEX IF NOT EXISTS modal_function_documents_index ON modal_function_documents USING GIN(mf_document);


CREATE OR REPLACE FUNCTION refresh_garden_documents()
RETURNS TRIGGER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW garden_documents;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql
;


CREATE OR REPLACE FUNCTION refresh_entrypoint_documents()
RETURNS TRIGGER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW entrypoint_documents;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql
;


CREATE OR REPLACE FUNCTION refresh_modal_function_documents()
RETURNS TRIGGER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW modal_function_documents;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql
;

CREATE OR REPLACE TRIGGER garden_documents_trigger
AFTER INSERT OR UPDATE OF authors,
                contributors,
                tags,
                description,
                title
ON gardens
EXECUTE FUNCTION refresh_garden_documents();


CREATE OR REPLACE TRIGGER entrypoint_documents_trigger
AFTER INSERT OR UPDATE OF authors,
                tags,
                description,
                title
ON entrypoints
EXECUTE FUNCTION refresh_entrypoint_documents();


CREATE OR REPLACE TRIGGER modal_function_documents_trigger
AFTER INSERT OR UPDATE OF authors,
                tags,
                description,
                title
ON modal_functions
EXECUTE FUNCTION refresh_modal_function_documents();

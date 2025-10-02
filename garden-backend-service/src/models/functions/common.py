from sqlalchemy import ARRAY, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column


class DoiMixin:
    doi: Mapped[str | None] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool] = mapped_column(default=True)
    is_archived: Mapped[bool] = mapped_column(default=False)


class AssociatedMaterialsMixin:
    # NOTE: modifications to these lists / dictionaries won't be picked up
    # by sqlalchemy ORM. Updates should replace with a copy.
    models: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    repositories: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    papers: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    datasets: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    notebooks: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))


class FunctionMetadataMixin:
    title: Mapped[str]
    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    description: Mapped[str | None]
    year: Mapped[str]
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    language: Mapped[str] = "en"
    version: Mapped[str] = "0.0.1"
    function_name: Mapped[str]
    function_text: Mapped[str]
    example_usage: Mapped[str | None]
    test_functions: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    conda_requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String))

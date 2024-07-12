from typing import Annotated, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    HttpUrl,
    PlainSerializer,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticCustomError


class BaseSchema(BaseModel, from_attributes=True):
    @field_validator("*", mode="before")
    @classmethod
    def use_default_if_none(cls, val, info: ValidationInfo) -> str:
        """validator for compatibility when parsing ORM instances with nullable attributes into response schemas.

        This means that `MySchema(optional_value=None)` behaves the same as
        simply omitting `optional_value` from the kwargs would

        (optional as in "not required", not optional as in "nullable". see
        https://docs.pydantic.dev/latest/migration/#required-optional-and-nullable-fields)
        """
        has_default: bool = not cls.model_fields[info.field_name].is_required()
        if val is None and has_default:
            val = cls.model_fields[info.field_name].get_default(
                call_default_factory=True
            )
        return val


T = TypeVar("T")


# see: https://github.com/pydantic/pydantic-core/pull/820#issuecomment-1670475909
def _validate_unique_list(v: list[T]) -> list[T]:
    if len(v) != len(set(v)):
        raise PydanticCustomError("unique_list", "List must be unique")
    return v


UniqueList = Annotated[
    list[T],
    AfterValidator(_validate_unique_list),
    Field(json_schema_extra={"uniqueItems": True}, default_factory=list),
]
Url = Annotated[HttpUrl, PlainSerializer(lambda url: str(url), return_type=type(""))]

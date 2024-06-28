from typing import Any, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import QueryableAttribute
from sqlalchemy.orm.relationships import RelationshipProperty

T = TypeVar("T", bound="Base")


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    @classmethod
    async def get(cls: Type[T], db: AsyncSession, **kwargs: Any) -> Optional[T]:
        q = select(cls)
        for field, value in kwargs.items():
            q = q.where(getattr(cls, field) == value)

        return (await db.execute(q)).scalar_one_or_none()

    @classmethod
    async def get_or_create(
        cls: Type[T], db: AsyncSession, **kwargs: Any
    ) -> tuple[T, bool]:
        obj = await cls.get(db, **kwargs)
        created = False

        if not obj:
            obj = cls(**kwargs)
            await obj._asave(db)
            await db.refresh(obj)
            created = True

        return obj, created

    async def _asave(self, db: AsyncSession) -> None:
        db.add(self)
        await db.flush()

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """
        Create an instance of the class from a dictionary, recursively handling nested dictionaries.

        Useful to instantiate from e.g. a nested pydantic model's `obj.model_dump()`.

        Args:
            data (dict): A dictionary of data to populate the instance. Nested dictionaries
                        representing relationships will be recursively converted to instances
                        of the related class.

        Returns:
            An instance of the class populated with the provided data.

        Raises:
            TypeError: If a key in the data dictionary is not a valid attribute of the class.
        """
        for key, value in data.items():
            if not hasattr(cls, key):
                # Raise an error if the class does not have an attribute named `key`
                raise TypeError(f"'{key}' is an invalid keyword argument for {cls}")

            orm_attribute: QueryableAttribute = getattr(cls, key)

            if isinstance(orm_attribute.property, RelationshipProperty):
                # if the attribute is a relationship, look up the related model class
                related_cls: Base = orm_attribute.property.mapper.class_

                if isinstance(value, dict):
                    # recursively convert a nested dictionary
                    data[key] = related_cls.from_dict(value)
                elif isinstance(value, list):
                    # recurse into list if elements are dicts
                    data[key] = [
                        related_cls.from_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
        return cls(**data)

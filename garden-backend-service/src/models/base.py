from typing import TypeVar, Type, Optional, Any
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession


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
    async def get_or_create(cls: Type[T], db: AsyncSession, **kwargs: Any) -> T:
        obj = await cls.get(db, **kwargs)

        if not obj:
            obj = cls(**kwargs)
            await obj._asave(db)
            await db.refresh(obj)

        return obj

    async def _asave(self, db: AsyncSession) -> None:
        db.add(self)
        await db.flush()

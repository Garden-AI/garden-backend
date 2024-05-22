from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession


class Base(AsyncAttrs, DeclarativeBase):

    @classmethod
    async def get(cls, db: AsyncSession, **kwargs):
        q = select(cls)
        for field, value in kwargs.items():
            q = q.where(getattr(cls, field) == value)

        return (await db.execute(q)).scalar_one_or_none()

    @classmethod
    async def get_or_create(cls, db: AsyncSession, **kwargs):
        obj = await cls.get(db, **kwargs)

        if not obj:
            obj = cls(**kwargs)
            await obj._asave(db)
            await db.refresh(obj)

        return obj

    async def _asave(self, db: AsyncSession):
        db.add(self)
        await db.flush()

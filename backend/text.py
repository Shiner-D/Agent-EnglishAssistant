import asyncio
from app.models.database import AsyncSessionLocal, init_db
from app.models.tables import WordbookWord, WordbookLevel
from sqlalchemy import select, update

async def clear():
    await init_db()
    async with AsyncSessionLocal() as db:
        lv = (await db.execute(select(WordbookLevel).where(WordbookLevel.name=='CET4'))).scalar_one()
        result = await db.execute(
            select(WordbookWord).where(WordbookWord.level_id==lv.id, WordbookWord.mnemonic.isnot(None)).limit(50)
        )
        words = result.scalars().all()
        for w in words:
            w.mnemonic = None
        await db.commit()
        print(f'Cleared {len(words)} mnemonics')

asyncio.run(clear())
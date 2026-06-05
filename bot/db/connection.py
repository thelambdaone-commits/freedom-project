import aiosqlite
from pathlib import Path
from bot.utils.config import settings
from bot.db.schema import CREATE_TABLES


async def get_connection() -> aiosqlite.Connection:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.executescript(CREATE_TABLES)
    await conn.commit()
    return conn

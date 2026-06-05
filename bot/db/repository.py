import json
from datetime import datetime
from typing import Optional
from bot.db.connection import get_connection
from bot.utils.crypto import encrypt, decrypt


async def ensure_user(telegram_id: int, username: str = ""):
    conn = await get_connection()
    await conn.execute(
        "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
        (telegram_id, username),
    )
    await conn.commit()
    await conn.close()


async def save_token(telegram_id: int, service: str, data: dict) -> int:
    conn = await get_connection()
    encrypted = encrypt(json.dumps(data))
    cursor = await conn.execute(
        "INSERT INTO tokens (telegram_id, service, encrypted_data) VALUES (?, ?, ?)",
        (telegram_id, service, encrypted),
    )
    await conn.commit()
    await conn.close()
    return cursor.lastrowid


async def get_token(telegram_id: int, service: str) -> Optional[dict]:
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT encrypted_data FROM tokens WHERE telegram_id = ? AND service = ? ORDER BY id DESC LIMIT 1",
        (telegram_id, service),
    )
    row = await cursor.fetchone()
    await conn.close()
    if row:
        return json.loads(decrypt(row["encrypted_data"]))
    return None


async def save_api_key(provider: str, api_key: str, base_url: str = "", source: str = "manual"):
    conn = await get_connection()
    encrypted = encrypt(api_key)
    await conn.execute(
        """INSERT INTO api_keys (provider, api_key_encrypted, base_url, source)
           VALUES (?, ?, ?, ?)""",
        (provider, encrypted, base_url, source),
    )
    await conn.commit()
    await conn.close()


async def get_active_api_keys(provider: Optional[str] = None) -> list[dict]:
    conn = await get_connection()
    if provider:
        cursor = await conn.execute(
            "SELECT * FROM api_keys WHERE provider = ? AND status = 'active' ORDER BY last_validated DESC",
            (provider,),
        )
    else:
        cursor = await conn.execute(
            "SELECT * FROM api_keys WHERE status = 'active' ORDER BY last_validated DESC"
        )
    rows = await cursor.fetchall()
    await conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["api_key"] = decrypt(d.pop("api_key_encrypted"))
        result.append(d)
    return result


async def update_api_key_status(key_id: int, status: str):
    conn = await get_connection()
    await conn.execute(
        "UPDATE api_keys SET status = ?, last_validated = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), key_id),
    )
    await conn.commit()
    await conn.close()


async def save_domain(telegram_id: int, domain: str, extension: str, status: str = "pending"):
    conn = await get_connection()
    await conn.execute(
        """INSERT OR REPLACE INTO domains (telegram_id, domain, extension, status)
           VALUES (?, ?, ?, ?)""",
        (telegram_id, domain, extension, status),
    )
    await conn.commit()
    await conn.close()


async def get_domains(telegram_id: int) -> list[dict]:
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT * FROM domains WHERE telegram_id = ? ORDER BY created_at DESC",
        (telegram_id,),
    )
    rows = await cursor.fetchall()
    await conn.close()
    return [dict(r) for r in rows]


async def save_session(telegram_id: int, service: str, session_data: dict):
    conn = await get_connection()
    encrypted = encrypt(json.dumps(session_data))
    await conn.execute(
        """INSERT OR REPLACE INTO sessions (telegram_id, service, session_data, last_used)
           VALUES (?, ?, ?, ?)""",
        (telegram_id, service, encrypted, datetime.utcnow().isoformat()),
    )
    await conn.commit()
    await conn.close()


async def get_session(telegram_id: int, service: str) -> Optional[dict]:
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT session_data FROM sessions WHERE telegram_id = ? AND service = ?",
        (telegram_id, service),
    )
    row = await cursor.fetchone()
    await conn.close()
    if row:
        return json.loads(decrypt(row["session_data"]))
    return None


async def log_action(telegram_id: int, action: str, status: str, details: str = ""):
    conn = await get_connection()
    await conn.execute(
        "INSERT INTO logs (telegram_id, action, status, details) VALUES (?, ?, ?, ?)",
        (telegram_id, action, status, details),
    )
    await conn.commit()
    await conn.close()


async def get_logs(limit: int = 20) -> list[dict]:
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    await conn.close()
    return [dict(r) for r in rows]

import aiosqlite
from config import DB_PATH

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Key-value store for bot-wide settings (e.g. instruction image file_id)
CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    num_emails      INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    emails          TEXT NOT NULL,          -- comma-separated email addresses
    payment_method  TEXT,                   -- 'CBE' | 'Telebirr'
    screenshot_file_id TEXT,               -- Telegram file_id of payment screenshot
    status          TEXT NOT NULL DEFAULT 'pending',
                                            -- pending | verified | rejected
    service_link    TEXT,                   -- filled by admin after verification
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

# ---------------------------------------------------------------------------
# Initialise
# ---------------------------------------------------------------------------

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SETTINGS_TABLE)
        await db.execute(CREATE_ORDERS_TABLE)
        await db.commit()


# ---------------------------------------------------------------------------
# Settings (key-value)
# ---------------------------------------------------------------------------

async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

async def create_order(
    user_id: int,
    username: str | None,
    full_name: str,
    num_emails: int,
    price: int,
    emails: list[str],
) -> int:
    """Insert a new pending order and return its id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (user_id, username, full_name, num_emails, price, emails)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, num_emails, price, ",".join(emails)),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def update_payment(
    order_id: int,
    payment_method: str,
    screenshot_file_id: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET payment_method = ?, screenshot_file_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payment_method, screenshot_file_id, order_id),
        )
        await db.commit()


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_pending_orders() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def verify_order(order_id: int, service_link: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET status = 'verified', service_link = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (service_link, order_id),
        )
        await db.commit()


async def reject_order(order_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (order_id,),
        )
        await db.commit()


async def get_user_orders(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

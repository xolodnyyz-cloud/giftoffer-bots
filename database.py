import aiosqlite
from typing import Optional, Dict, Any, List

DB_PATH = "deals.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS deals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id    INTEGER NOT NULL,
    seller_name  TEXT    NOT NULL,
    buyer_id     INTEGER,
    buyer_name   TEXT,
    gift_url     TEXT    NOT NULL,
    gift_name    TEXT    NOT NULL,
    gift_number  TEXT    NOT NULL,
    price        INTEGER NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'created',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()

async def create_deal(seller_id: int, seller_name: str, gift_url: str, gift_name: str, gift_number: str, price: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO deals (seller_id, seller_name, gift_url, gift_name, gift_number, price, status)
            VALUES (?, ?, ?, ?, ?, ?, 'created')
            """,
            (seller_id, seller_name, gift_url, gift_name, gift_number, price),
        )
        await db.commit()
        return cursor.lastrowid

async def get_deal(deal_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def accept_deal(deal_id: int, buyer_id: int, buyer_name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE deals SET buyer_id = ?, buyer_name = ?, status = 'accepted' WHERE id = ? AND status = 'created'",
            (buyer_id, buyer_name, deal_id),
        )
        await db.commit()
        return cursor.rowcount > 0

async def reject_deal(deal_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("UPDATE deals SET status = 'rejected' WHERE id = ? AND status = 'created'", (deal_id,))
        await db.commit()
        return cursor.rowcount > 0

async def set_waiting_transfer(deal_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deals SET status = 'waiting_transfer' WHERE id = ?", (deal_id,))
        await db.commit()

async def complete_deal(deal_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE deals SET status = 'completed' WHERE id = ? AND status IN ('accepted', 'waiting_transfer')",
            (deal_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
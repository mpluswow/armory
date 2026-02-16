from contextlib import asynccontextmanager

import aiomysql

from config import settings

pool: aiomysql.Pool | None = None


async def create_pool():
    global pool
    pool = await aiomysql.create_pool(
        host=settings.DB_HOST,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        db=settings.DB_NAME,
        charset="utf8mb4",
        minsize=2,
        maxsize=10,
        autocommit=True,
        cursorclass=aiomysql.DictCursor,
    )


async def close_pool():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        pool = None


@asynccontextmanager
async def get_conn():
    async with pool.acquire() as conn:
        yield conn

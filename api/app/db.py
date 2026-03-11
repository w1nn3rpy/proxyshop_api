import asyncpg
from decouple import config

DB_URL = config('DATABASE_URL')

pool = None

async def init_db():
    global pool

    pool = await asyncpg.create_pool(
        DB_URL,
        min_size=1,
        max_size=10
    )


async def get_pool():
    return pool
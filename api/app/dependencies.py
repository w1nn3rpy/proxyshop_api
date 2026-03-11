from fastapi import Header, HTTPException, Depends
from fastapi.security import APIKeyHeader
from api.app.db import get_pool

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_user(api_key: str = Depends(api_key_header)):

    pool = await get_pool()

    async with pool.acquire() as conn:

        user = await conn.fetchrow(
            """
            SELECT *
            FROM api_users
            WHERE api_key=$1
            """,
            api_key
        )

    if not user:
        raise HTTPException(401, "Invalid API key")

    return user
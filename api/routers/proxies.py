from fastapi import APIRouter, Depends
from api.app.dependencies import get_api_user
from api.app.db import get_pool

router = APIRouter(prefix="/api")


@router.get(
    "/proxies",
    summary="Get all purchased proxies",
    description="Returns all proxies previously purchased by the API user"
)
async def get_user_proxies(user=Depends(get_api_user)):

    pool = await get_pool()

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                proxy_id,
                ip_address,
                username,
                password,
                country,
                city,
                state,
                zipcode,
                proxy_type,
                price,
                date
            FROM api_orders
            WHERE user_id = $1
            ORDER BY date DESC
            """,
            user["user_id"]
        )

    proxies = []

    for r in rows:
        proxies.append({
            "proxy_id": r["proxy_id"],
            "ip": r["ip_address"],
            "login": r["username"],
            "password": r["password"],
            "country": r["country"],
            "city": r["city"],
            "state": r["state"],
            "zipcode": r["zipcode"],
            "type": r["proxy_type"],
            "price": r["price"],
            "date": r["date"]
        })

    return {
        "total": len(proxies),
        "proxies": proxies
    }
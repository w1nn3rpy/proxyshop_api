from fastapi import APIRouter, Depends, HTTPException
from api.schemas.order import OrderCreate
from api.app.dependencies import get_api_user
from api.app.db import get_pool

router = APIRouter(prefix="/api")


@router.post(
    "/orders",
    summary="Buy proxies",
    description="Purchase proxies with filtering by country, city, state and zip"
)
async def create_order(order: OrderCreate, user=Depends(get_api_user)):

    pool = await get_pool()

    # определяем цену
    price_map = {
        "res": user["res_price"],
        "def": user["def_price"],
        "nondef": user["nondef_price"]
    }

    price = price_map[order.type]

    total_price = price * order.quantity

    if user["balance"] < total_price:
        raise HTTPException(400, "Insufficient balance")

    async with pool.acquire() as conn:

        filters = ["s.country = $1", "s.proxy_type = $2"]
        values = [order.country, order.type]

        param_index = 3

        if order.city:
            filters.append(f"s.city = ${param_index}")
            values.append(order.city)
            param_index += 1

        if order.state:
            filters.append(f"s.state = ${param_index}")
            values.append(order.state)
            param_index += 1

        if order.zip:
            filters.append(f"s.zipcode = ${param_index}")
            values.append(order.zip)
            param_index += 1

        query = f"""
        SELECT s.*
        FROM shop s
        WHERE {" AND ".join(filters)}

        AND NOT EXISTS (
            SELECT 1
            FROM api_orders o
            WHERE o.proxy_id = s.id
            AND o.user_id = ${param_index}
        )

        LIMIT {order.quantity}
        """

        values.append(user["user_id"])

        proxies = await conn.fetch(query, *values)

        if len(proxies) < order.quantity:
            raise HTTPException(
                400,
                f"Only {len(proxies)} proxies available"
            )

        async with conn.transaction():

            for proxy in proxies:

                await conn.execute(
                    """
                    INSERT INTO api_orders
                    (
                        user_id,
                        proxy_id,
                        country,
                        city,
                        state,
                        proxy_type,
                        ip_address,
                        username,
                        password,
                        zipcode,
                        price
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    """,
                    user["user_id"],
                    proxy["id"],
                    proxy["country"],
                    proxy["city"],
                    proxy["state"],
                    proxy["type"],
                    proxy["ip"],
                    proxy["login"],
                    proxy["password"],
                    proxy["zipcode"],
                    price
                )

            await conn.execute(
                """
                UPDATE api_users
                SET balance = balance - $1
                WHERE user_id=$2
                """,
                total_price,
                user["user_id"]
            )

    result = []

    for p in proxies:
        result.append(
            {
                "ip": p["ip"],
                "port": p["port"],
                "login": p["login"],
                "password": p["password"],
                "country": p["country"],
                "city": p["city"],
                "state": p["state"],
                "zipcode": p["zipcode"]
            }
        )

    return {
        "quantity": len(result),
        "price_per_proxy": price,
        "total_price": total_price,
        "proxies": result
    }
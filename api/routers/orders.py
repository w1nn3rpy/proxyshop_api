import asyncio

from fastapi import APIRouter, Depends, HTTPException
from api.schemas.order import OrderCreate
from api.app.dependencies import get_api_user
from api.app.db import get_pool
from api.utils.proxy_check import ping_port
from datetime import datetime

router = APIRouter(prefix="/api")

async def check_proxy_db(proxy: dict, port: int = 1723, timeout: int = 20) -> bool:
    """
    Проверяет прокси через TCP.
    """
    return await ping_port(proxy["ip_address"], port=port, timeout=timeout)


async def filter_and_validate_proxies(proxies, needed):

    tasks = [
        ping_port(p["ip_address"], 1723)
        for p in proxies
    ]

    results = await asyncio.gather(*tasks)

    working = []
    invalid = []

    for proxy, ok in zip(proxies, results):

        if ok:
            working.append(proxy)
        else:
            invalid.append(proxy)

        if len(working) >= needed:
            break

    return working, invalid

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
    if order.type not in price_map:
        raise HTTPException(400, "Invalid proxy type")

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

        user_param_index = param_index
        values.append(user["user_id"])

        desired_qty = order.quantity
        working_proxies = []
        invalid_proxies = []

        while len(working_proxies) < desired_qty:
            remaining_qty = desired_qty - len(working_proxies)

            # query = f"""
            # SELECT s.*
            # FROM shop s
            # WHERE {" AND ".join(filters)}
            #
            # AND NOT EXISTS (
            #     SELECT 1
            #     FROM api_orders o
            #     WHERE o.proxy_id = s.id
            #     AND o.user_id = ${user_param_index}
            # )
            #
            # LIMIT {remaining_qty}
            # """
            query = """
                    SELECT *
                    FROM shop LIMIT 20 \
                    """
            batch = await conn.fetch(query)

            # batch = await conn.fetch(query, *values)
            if not batch:
                print("NO PROXIES FROM DB")
                break  # больше нет подходящих прокси
            batch_dicts = [dict(p) for p in batch]

            print("PROXIES FROM DB:", len(batch_dicts))

            working, invalid = await filter_and_validate_proxies(batch_dicts, remaining_qty)
            working_proxies.extend(working)
            invalid_proxies.extend(invalid)

            # Перемещаем невалидные прокси в таблицу invalid
            for p in invalid:
                await conn.execute(
                    """
                    INSERT INTO invalid
                    (id, ip_address, username, password, country, city, state, zipcode, proxy_type, price, validation_date, reason)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    p["id"], p["ip_address"], p["username"], p["password"], p["country"], p["city"], p["state"], p["zipcode"], p["proxy_type"],
                    price, datetime.now(), "failed validation"
                )
                # удаляем из shop
                await conn.execute("DELETE FROM shop WHERE id = $1", p["id"])

        if len(working_proxies) < desired_qty:
            raise HTTPException(
                400,
                f"Only {len(working_proxies)} working proxies available"
            )

        async with conn.transaction():

            for proxy in working_proxies:

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
                    proxy["proxy_type"],
                    proxy["ip_address"],
                    proxy["username"],
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

    result = [
        {
            "ip": p["ip_address"],
            "login": p["username"],
            "password": p["password"],
            "country": p["country"],
            "city": p["city"],
            "state": p["state"],
            "zipcode": p["zipcode"]
        }
        for p in working_proxies
    ]

    return {
        "quantity": len(result),
        "price_per_proxy": price,
        "total_price": total_price,
        "proxies": result
    }
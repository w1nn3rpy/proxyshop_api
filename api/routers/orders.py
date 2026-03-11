import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from api.schemas.order import OrderCreate
from api.app.dependencies import get_api_user
from api.app.db import get_pool
from api.utils.proxy_check import ping_port

router = APIRouter(prefix="/api")


async def filter_and_validate_proxies(proxies, needed):
    """
    Проверка списка прокси. Возвращает кортеж (валидные, невалидные)
    """
    tasks = [ping_port(p["ip_address"], 1723) for p in proxies]
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
    print('открыли пул')
    # Определяем цену
    price_map = {
        "res": user["res_price"],
        "def": user["def_price"],
        "nondef": user["nondef_price"]
    }
    print('определили цену')
    if order.type not in price_map:
        raise HTTPException(400, "Invalid proxy type")

    price = price_map[order.type]
    print('price = ', price)
    total_price = price * order.quantity
    print('total_price = ', total_price)

    if user["balance"] < total_price:
        raise HTTPException(400, "Insufficient balance")
    print('баланс норм')

    async with pool.acquire() as conn:

        # Формируем фильтры
        filters = ["s.country = $1", "s.proxy_type = $2"]
        values = [order.country, order.type]
        param_index = 3
        print('сформировали фильтры')
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
        print('84 строка')

        desired_qty = order.quantity
        working_proxies = []
        invalid_proxies = []
        already_taken_ids = set()
        print('88 строка')
        while len(working_proxies) < desired_qty:
            remaining_qty = desired_qty - len(working_proxies)
            print('91 строка')
            # Берем только прокси с фильтрами и которые ещё не куплены пользователем
            query = f"""
                SELECT s.*
                FROM shop s
                WHERE {" AND ".join(filters)}
                  AND NOT EXISTS (
                      SELECT 1
                      FROM api_orders o
                      WHERE o.proxy_id = s.id
                      AND o.user_id = ${user_param_index}
                  )
                  ORDER BY RANDOM()
                LIMIT {remaining_qty * 5}
            """
            batch = await conn.fetch(query, *values)
            print('бачнули')
            if not batch:
                print('нот бач')
                break

            batch_dicts = [dict(p) for p in batch]
            batch_dicts = [p for p in batch_dicts if p["id"] not in already_taken_ids]

            print('бач диктс', batch_dicts)
            # Проверяем валидность
            working, invalid = await filter_and_validate_proxies(batch_dicts, remaining_qty)
            working_proxies.extend(working)
            invalid_proxies.extend(invalid)

            for p in working:
                already_taken_ids.add(p["id"])

            print('проверили валидность')
            # Перемещаем невалидные в таблицу invalid и удаляем из shop
            for p in invalid:
                await conn.execute(
                    """
                    INSERT INTO invalid
                    (id, ip_address, username, password, country, city, state, zipcode, proxy_type, price, validation_date, reason)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    p["id"], p["ip_address"], p["username"], p["password"],
                    p["country"], p["city"], p["state"], p["zipcode"],
                    p["proxy_type"], price, datetime.now(), "failed validation"
                )
                await conn.execute("DELETE FROM shop WHERE id = $1", p["id"])

        if len(working_proxies) < desired_qty:
            print('len working < desired')
            raise HTTPException(
                400,
                f"Only {len(working_proxies)} working proxies available"
            )

        # Создаем заказы и списываем баланс
        async with conn.transaction():
            for proxy in working_proxies:
                await conn.execute(
                    """
                    INSERT INTO api_orders
                    (user_id, proxy_id, country, city, state, proxy_type, ip_address, username, password, zipcode, price)
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
                "UPDATE api_users SET balance = balance - $1 WHERE user_id=$2",
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
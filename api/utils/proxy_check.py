import asyncio

async def ping_port(ip: str, port: int = 1723, timeout: int = 20) -> bool:
    """
    Проверяет доступность TCP-порта через nmap.
    Возвращает True, если порт открыт, False если закрыт.
    """
    cmd = ["nmap", "-Pn", "-n", "-p", str(port), "--open", "--host-timeout", f"{timeout}s", ip]

    try:
        # Асинхронный вызов nmap
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode()
        # Проверяем статус порта в выводе nmap
        if "open" in output:
            return True
        else:
            return False

    except Exception:
        return False

async def check_proxy(proxy: dict, port: int = 1723, timeout: int = 20) -> bool:
    """
    Проверяет прокси по IP и порту. Возвращает True, если прокси рабочая.
    proxy = {
        "ip": str,
        "port": int,
        "login": str,
        "password": str,
        ...
    }
    """
    return await ping_port(proxy["ip"], proxy.get("port", port), timeout)

async def filter_working_proxies(proxies: list[dict], max_checks: int = None) -> list[dict]:
    """
    Фильтрует только рабочие прокси из списка.
    max_checks — ограничение по количеству проверок (например quantity).
    """
    if max_checks:
        proxies = proxies[:max_checks]

    results = await asyncio.gather(*(check_proxy(p) for p in proxies))
    working = [p for p, ok in zip(proxies, results) if ok]
    return working
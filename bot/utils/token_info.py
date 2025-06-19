import aiohttp
from datetime import datetime

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"


def shorten(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"


def format_number(value: float) -> str:
    """Красиво форматируем число с округлением до K/M без лишней точности."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.0f}K"
    else:
        return f"${int(value)}"


async def fetch_token_info(ca: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(DEX_API + ca) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if not pairs:
                        return None

                    token = max(
                        pairs,
                        key=lambda p: float(p.get("liquidity", {}).get("usd", 0.0))
                    )
                    base = token.get("baseToken", {})

                    return {
                        "name": base.get("name", "Unknown"),
                        "symbol": base.get("symbol", ""),
                        "ca": ca,
                        "price": float(token.get("priceUsd", 0.0)),
                        "fdv": float(token.get("fdv", 0.0)),
                        "liquidity": float(token.get("liquidity", {}).get("usd", 0.0)),
                        "icon": token.get("info", {}).get("openGraph"),
                        "volume": {
                            "24ч": float(token.get("volume", {}).get("h24", 0)),
                            "6ч": float(token.get("volume", {}).get("h6", 0)),
                            "1ч": float(token.get("volume", {}).get("h1", 0)),
                            "5м": float(token.get("volume", {}).get("m5", 0)),
                        }
                    }
                except Exception as e:
                    print(f"❌ Ошибка при парсинге: {e}")
                    return None
            return None


def format_token_info_message(data: dict, updated_at: datetime | None = None, include_link: bool = True) -> str:
    vol = data.get("volume", {})
    ca = data['ca']

    # Готовим выравнивание объёмов по правому краю
    values = {k: format_number(v) for k, v in vol.items()}
    max_len = max(len(v) for v in values.values()) if values else 0

    volume_lines = "\n".join(
        f"<code>• {label:<3}:       {value:>{max_len}}</code>"
        for label, value in values.items()
    )

    # Линия со временем обновления
    updated_line = (
        f"\n\n⏱️ Last updated at {updated_at.strftime('%H:%M:%S')} UTC"
        if updated_at else ""
    )

    # Ссылка на Dexscreener (опционально)
    link_line = (
        f"\n\n🔗 <b><a href='https://dexscreener.com/solana/{ca}'>Dexscreener</a></b>"
        if include_link else ""
    )

    return (
        f"💠 Token: <code>${data['symbol']} ({data['name']})</code>\n\n"
        f"🧾 <b>CA:</b> <code>{ca}</code>\n"
        f"💵 <b>Цена:</b> ${data['price']:.8f}\n"
        f"💰 <b>Рыночная капитализация:</b> {format_number(data['fdv'])}\n"
        f"💧 <b>Ликвидность:</b> {format_number(data['liquidity'])}\n\n"
        f"📊 <b>Объёмы:</b>\n{volume_lines}"
        f"{link_line}"
        f"{updated_line}"
    )

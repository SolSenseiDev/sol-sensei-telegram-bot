from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_wallets_keyboard(wallets: list, balances: dict, selected: str = None) -> InlineKeyboardMarkup:
    keyboard = []

    for i, wallet in enumerate(wallets, start=1):
        addr = wallet.address
        short_addr = addr[:4] + "..." + addr[-4:]
        label = f"({i}) ✅ {short_addr}" if selected == addr else f"({i}) {short_addr}"
        balance = balances.get(addr, 0)

        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"select_wallet:{addr}"),
            InlineKeyboardButton(text=f"{balance:.3f} SOL", callback_data="noop")
        ])

    keyboard.append([
        InlineKeyboardButton(text="➕ Создать кошелек", callback_data="new_wallet"),
        InlineKeyboardButton(text="❌ Удалить выбранный", callback_data="delete_wallet")
    ])

    keyboard.append([
        InlineKeyboardButton(text="📤 Вывести весь SOL", callback_data="withdraw_all")
    ])

    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

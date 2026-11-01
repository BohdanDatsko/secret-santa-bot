from typing import ClassVar

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import async_sessionmaker


class DatabaseSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def __call__(self, handler, event: TelegramObject, data: dict):
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class PrivateChatMiddleware(BaseMiddleware):
    private_commands: ClassVar[set[str]] = {
        "/start",
        "/admin",
        "/new_game",
        "/cancel_game",
        "/retry_notifications",
        "/wishlist",
        "/gift",
        "/cancel",
    }

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Update):
            message = event.message
            if message is not None and message.chat.type != "private":
                command = (
                    message.text.split(maxsplit=1)[0].split("@", 1)[0] if message.text else None
                )
                if command in self.private_commands:
                    await message.answer("Будь ласка, використовуйте приватний чат із ботом.")
                return None
            callback = event.callback_query
            if callback is not None and (
                callback.message is None or callback.message.chat.type != "private"
            ):
                await callback.answer(
                    "Будь ласка, використовуйте приватний чат із ботом.",
                    show_alert=True,
                )
                return None
        return await handler(event, data)

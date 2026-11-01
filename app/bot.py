import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.handlers import admin, draw, pairs, participants, start, wishlist
from app.middleware import DatabaseSessionMiddleware, PrivateChatMiddleware
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    session_factory: async_sessionmaker,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(PrivateChatMiddleware())
    dispatcher.update.middleware(DatabaseSessionMiddleware(session_factory))
    routers = (
        start.router,
        admin.router,
        participants.router,
        pairs.router,
        draw.router,
        wishlist.router,
    )
    for router in routers:
        dispatcher.include_router(router)

    @dispatcher.errors()
    async def handle_update_error(event: ErrorEvent, exception: Exception) -> bool:
        if isinstance(exception, ServiceError):
            response = str(exception)
        elif isinstance(exception, SQLAlchemyError):
            logger.error(
                "Database operation failed while processing an update (error=%s)",
                type(exception).__name__,
            )
            response = "Тимчасова помилка бази даних. Спробуйте ще раз пізніше."
        else:
            logger.error(
                "Update processing failed (error=%s)",
                type(exception).__name__,
            )
            response = "Не вдалося виконати дію. Спробуйте ще раз."

        if event.update.message is not None:
            await event.update.message.answer(response)
        elif event.update.callback_query is not None:
            await event.update.callback_query.answer(response, show_alert=True)
        return True

    return dispatcher

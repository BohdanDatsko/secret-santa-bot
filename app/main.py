import asyncio
import logging

from aiogram.types import BotCommand
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.bot import create_bot, create_dispatcher
from app.config import get_settings
from app.database.session import create_database
from app.services.outbox_service import run_outbox_worker


async def wait_for_database(engine) -> None:
    delay = 1
    while True:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except SQLAlchemyError as error:
            logging.getLogger(__name__).warning(
                "Database unavailable; retrying (error=%s)",
                type(error).__name__,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine, session_factory = create_database(settings)
    bot = create_bot(settings)
    dispatcher = create_dispatcher(session_factory)
    tasks = ()
    try:
        await wait_for_database(engine)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Зареєструватися"),
                BotCommand(command="admin", description="Меню організатора"),
                BotCommand(command="wishlist", description="Редагувати wishlist"),
                BotCommand(command="gift", description="Переглянути wishlist отримувача"),
                BotCommand(command="cancel", description="Скасувати поточне введення"),
            ]
        )
        polling_task = asyncio.create_task(dispatcher.start_polling(bot))
        outbox_task = asyncio.create_task(run_outbox_worker(bot, session_factory))
        tasks = (polling_task, outbox_task)
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

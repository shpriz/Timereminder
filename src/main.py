import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from src.bot import create_bot_app
from src.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="NARFU Schedule Reminder")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def main() -> None:
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    bot_app = create_bot_app()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    logger.info("Telegram bot started")

    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    logger.info("FastAPI server starting on :8001")

    try:
        await server.serve()
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        scheduler.shutdown()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

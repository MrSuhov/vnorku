import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from config.settings import settings
from shared.utils.unified_logging import setup_service_logging
import uvicorn

setup_service_logging('promotion-service', level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Korzinka Promotion Service",
    description="Сервис управления промокодами и скидками", 
    version="1.0.0"
)


@app.get("/promotions/collect")
async def collect_promotions():
    """Сбор актуальных промокодов"""
    # TODO: Реализовать сбор промокодов через OpenAI
    return {"success": True, "message": "Promotions collected"}


@app.get("/health") 
async def health_check():
    return {"status": "healthy", "service": "promotion-service"}


async def run_service():
    logger.info(f"🚀 Starting Promotion Service on port {settings.promotion_service_port}")
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.promotion_service_port, 
        log_config=None,
        access_log=settings.debug
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run_service())

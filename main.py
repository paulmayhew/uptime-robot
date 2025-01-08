import asyncio
import logging
from contextlib import asynccontextmanager

from a2wsgi import ASGIMiddleware
from fastapi import FastAPI

from components.mysql_table_monitor import monitor_sql_table, DatabaseMonitor
from components.site_uptime_monitor import monitor_urls
from utils.config import Settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings()
    monitor_task = asyncio.create_task(monitor_tasks(settings))
    yield
    monitor_task.cancel()
    await DatabaseMonitor.close()


app = FastAPI(lifespan=lifespan)


async def monitor_tasks(settings: Settings):
    try:
        await asyncio.gather(
            monitor_sql_table(settings),
            monitor_urls()
        )
    except Exception as e:
        logging.error(f"Monitoring failed: {e}")


@app.get("/")
async def health_check():
    return {"status": "running"}


wsgi_app = ASGIMiddleware(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False
    )

"""FastAPI app: job submission, SSE progress, artifact serving. The
pipeline itself (app/pipeline/, app/cli.py's sibling here is
app/server/pipeline_runner.py) knows nothing about HTTP/Mongo/Redis - this
module and app/worker.py are the two processes that wrap it.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.server.config import get_settings
from app.server.db import connect_database
from app.server.net_utils import host_only
from app.server.pubsub import connect_redis
from app.server.queue import connect_queue
from app.server.routes import events, files, jobs, meta
from app.server.security import SecretRedactingFilter
from app.server.startup_checks import check_render_dependencies

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app.main")
logging.getLogger().addFilter(SecretRedactingFilter())


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            return JSONResponse(status_code=413, content={"detail": "request body too large"})
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    check_render_dependencies()
    logger.info(
        "api starting: redis=%s mongo=%s",
        host_only(settings.redis_url),
        host_only(settings.mongo_url),
    )
    await connect_database(settings)
    await connect_redis(settings.redis_url)
    await connect_queue(settings.redis_url)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="video-pipeline", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)

    app.include_router(meta.router)
    app.include_router(jobs.router)
    app.include_router(events.router)
    app.include_router(files.router)
    return app


app = create_app()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import create_pool, close_pool
from routes.characters import router as characters_router
from routes.models import router as models_router


def _warmup_mpq_pool():
    """Pre-open all MPQ archives at startup so first requests aren't slow."""
    import os, sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "Data")
    tools_dir = os.path.join(project_root, "tools")
    sys.path.insert(0, tools_dir)
    try:
        from extract_models import _get_mpq, MPQ_LOAD_ORDER
        for mpq_name in MPQ_LOAD_ORDER:
            mpq_path = os.path.join(data_dir, mpq_name)
            if os.path.exists(mpq_path):
                _get_mpq(mpq_path)
        print(f"MPQ pool warmed up ({len(MPQ_LOAD_ORDER)} archives)")
    except Exception as e:
        print(f"MPQ warmup failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warmup_mpq_pool()
    await create_pool()
    yield
    await close_pool()


app = FastAPI(title="AzerothCore Armory", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(characters_router)
app.include_router(models_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

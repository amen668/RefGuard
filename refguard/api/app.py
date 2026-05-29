"""FastAPI app: /api/v1/verify/bib, /api/v1/verify/project, /api/v1/sources/status."""
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from refguard import __version__
from refguard.services import VerificationService
from refguard.core import cache_manager, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="RefGuard API", version=__version__)
    app.include_router(verify_router, prefix="/api/v1", tags=["verify"])
    app.include_router(sources_router, prefix="/api/v1", tags=["sources"])
    return app


# --- Schemas ---
class VerifyBibOptions(BaseModel):
    check_duplicates: bool = True
    top_k_candidates: int = 8


class VerifyBibRequest(BaseModel):
    bibtex_content: str = Field(..., min_length=1)
    profile: str = Field(default="balanced", pattern="^(strict|balanced|lenient)$")
    options: VerifyBibOptions = Field(default_factory=VerifyBibOptions)


class VerifyBibResponse(BaseModel):
    summary: dict
    entries: list
    duplicates: list
    run_metadata: Optional[dict] = None


class SourcesStatusResponse(BaseModel):
    cache: dict
    sources: list


# --- Routes ---
from fastapi import APIRouter
verify_router = APIRouter()
sources_router = APIRouter()


@verify_router.post("/verify/bib", response_model=VerifyBibResponse)
def post_verify_bib(req: VerifyBibRequest) -> dict:
    try:
        svc = VerificationService(profile_name=req.profile, top_k=req.options.top_k_candidates)
        report = svc.verify_bib(req.bibtex_content, check_duplicates=req.options.check_duplicates)
        data = report.to_json()
        return {
            "summary": data["summary"],
            "entries": data["entries"],
            "duplicates": data["duplicates"],
            "run_metadata": data.get("run_metadata"),
        }
    except Exception as e:
        logger.exception("verify/bib failed")
        raise HTTPException(status_code=500, detail=str(e))


class VerifyProjectRequest(BaseModel):
    bib_content: str = Field(..., min_length=1)
    tex_paths: Optional[list[str]] = None
    profile: str = "balanced"
    check_usage: bool = True


@verify_router.post("/verify/project")
def post_verify_project(req: VerifyProjectRequest) -> dict:
    try:
        svc = VerificationService(profile_name=req.profile)
        report = svc.verify_project(req.bib_content, tex_paths=req.tex_paths or [], check_usage=req.check_usage)
        return report.to_json()
    except Exception as e:
        logger.exception("verify/project failed")
        raise HTTPException(status_code=500, detail=str(e))


@sources_router.get("/sources/status", response_model=SourcesStatusResponse)
def get_sources_status() -> dict:
    cache_stats = cache_manager.get_stats()
    return {
        "cache": cache_stats,
        "sources": ["crossref", "openalex", "arxiv", "semanticscholar", "dblp"],
    }


app = create_app()

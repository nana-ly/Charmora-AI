from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.catalog import get_db
from db.models import VectorSyncJob
from retrieval.vector import VectorRetriever
from services.vector_sync_service import VectorSyncService

router = APIRouter(prefix="/vector-sync", tags=["vector-sync"])


@router.get("/status")
def vector_sync_status(session: Session = Depends(get_db)) -> dict:
    rows = session.execute(
        select(VectorSyncJob.status, func.count(VectorSyncJob.id)).group_by(VectorSyncJob.status)
    ).all()
    counts = {status: count for status, count in rows}
    return {
        "pending": counts.get("pending", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
    }


@router.post("/run")
def run_vector_sync(
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    index = VectorRetriever().store
    return VectorSyncService(session, index).process_pending(limit)


@router.post("/retry-failed")
def retry_failed_vector_sync(
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    return {"retried": VectorSyncService(session, VectorRetriever().store).retry_failed(limit)}

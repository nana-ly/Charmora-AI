from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from api.catalog import get_db
from core.errors import AppError
from schemas.imports import ImportBatchListResponse, ImportBatchView
from services.import_parsers import parse_product_file_result
from services.product_import_service import ProductImportService

router = APIRouter(prefix="/imports", tags=["imports"])
MAX_IMPORT_BYTES = 20 * 1024 * 1024


@router.post("/products", response_model=ImportBatchView)
async def import_products(
    file: UploadFile = File(...),
    source_key: str = Form("local-file"),
    source_name: str = Form("本地文件导入"),
    default_inventory: int = Form(0, ge=0),
    session: Session = Depends(get_db),
) -> ImportBatchView:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise AppError("import_file_too_large", "导入文件不能超过 20MB。", status_code=413)
    try:
        parsed = parse_product_file_result(
            content,
            file.filename or "products.json",
            default_inventory=default_inventory,
        )
    except Exception as exc:
        raise AppError(
            "invalid_import_file",
            "导入文件格式或内容无效。",
            details={"reason": str(exc)},
        ) from exc
    return ProductImportService(session).import_records(
        source_key=source_key,
        source_name=source_name,
        source_type="file",
        filename=file.filename,
        records=parsed.records,
        parse_errors=parsed.errors,
        total_count=parsed.total_count,
    )


@router.get("", response_model=ImportBatchListResponse)
def list_import_batches(
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> ImportBatchListResponse:
    items = ProductImportService(session).list_batches(
        status=status, offset=offset, limit=limit
    )
    return ImportBatchListResponse(items=items, offset=offset, limit=limit)


@router.get("/{batch_id}", response_model=ImportBatchView)
def get_import_batch(batch_id: UUID, session: Session = Depends(get_db)) -> ImportBatchView:
    batch = ProductImportService(session).get_batch(batch_id)
    if batch is None:
        raise AppError("import_batch_not_found", "导入批次不存在。", status_code=404)
    return batch

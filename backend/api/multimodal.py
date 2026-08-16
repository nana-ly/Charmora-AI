from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.catalog import get_db
from core.config import load_app_config
from schemas.multimodal import (
    AsrResponse,
    ImageSearchResponse,
    ImageUnderstandingResponse,
    TtsRequest,
)
from services.multimodal_service import MultimodalService

router = APIRouter(prefix="/multimodal", tags=["multimodal"])


def service(session: Session = Depends(get_db)) -> MultimodalService:
    return MultimodalService(load_app_config().multimodal, session)


@router.post("/images/understand", response_model=ImageUnderstandingResponse)
async def understand_image(
    file: UploadFile = File(...),
    prompt: str = Form("识别图片中的商品类型、外观特征和适用购物关键词。"),
    multimodal: MultimodalService = Depends(service),
) -> ImageUnderstandingResponse:
    content = await file.read(multimodal.config.max_image_bytes + 1)
    asset_id, description = multimodal.understand_image(
        content, file.content_type or "application/octet-stream", prompt
    )
    return ImageUnderstandingResponse(asset_id=asset_id, description=description)


@router.post("/images/search", response_model=ImageSearchResponse)
async def search_image(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=20),
    multimodal: MultimodalService = Depends(service),
) -> ImageSearchResponse:
    content = await file.read(multimodal.config.max_image_bytes + 1)
    asset_id, items = multimodal.search_image(
        content, file.content_type or "application/octet-stream", top_k
    )
    return ImageSearchResponse(asset_id=asset_id, items=items)


@router.post("/asr", response_model=AsrResponse)
async def speech_to_text(
    file: UploadFile = File(...),
    multimodal: MultimodalService = Depends(service),
) -> AsrResponse:
    content = await file.read(multimodal.config.max_audio_bytes + 1)
    return AsrResponse(
        text=multimodal.transcribe(content, file.content_type or "application/octet-stream")
    )


@router.post("/tts")
def text_to_speech(
    request: TtsRequest,
    multimodal: MultimodalService = Depends(service),
) -> Response:
    return Response(content=multimodal.synthesize(request.text), media_type="audio/mpeg")

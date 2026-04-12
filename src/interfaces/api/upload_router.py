"""
Endpoint para subir imágenes al chat (pre-upload antes de enviar mensaje).
"""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from infra.tools.s3_client import upload_image_bytes
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int


@router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    """Sube una imagen y retorna la URL de S3."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed",
        )

    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be under 10MB",
        )

    try:
        result = await upload_image_bytes(
            image_bytes=contents,
            content_type=file.content_type,
            org_id=org_id,
            prefix="chat-uploads",
        )
        return UploadResponse(
            url=result["url"],
            filename=file.filename or "image",
            content_type=file.content_type,
            size=len(contents),
        )
    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image upload failed",
        )
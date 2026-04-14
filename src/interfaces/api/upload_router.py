"""
Endpoint para subir imágenes al chat (pre-upload antes de enviar mensaje).

Soporta dos modos:
- Persistente (default): sube a S3 y devuelve URL pública.
- Efímero (ephemeral=true): NO toca S3, retorna data URL base64.
  Pensado para imágenes de referencia en flows / batch que se usan
  solo como contexto visual y no deben quedar en el bucket.
"""

import base64
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from pydantic import BaseModel

from infra.tools.s3_client import upload_image_bytes
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# Tope inferior para uploads efímeros (van por header en SSE / multipart en context).
# Imágenes muy grandes infladas a base64 explotan el payload del request al LLM.
EPHEMERAL_MAX_SIZE = 4 * 1024 * 1024   # 4MB
PERSISTENT_MAX_SIZE = 10 * 1024 * 1024  # 10MB


class UploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int
    ephemeral: bool = False


@router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    ephemeral: bool = Query(
        default=False,
        description="Si true, retorna data URL base64 sin tocar S3. Para imágenes de referencia transitorias (flows, batch).",
    ),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    """Sube una imagen y retorna URL S3 (default) o data URL base64 (ephemeral)."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed",
        )

    max_size = EPHEMERAL_MAX_SIZE if ephemeral else PERSISTENT_MAX_SIZE
    contents = await file.read()
    if len(contents) > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be under {limit_mb}MB",
        )

    # ── Modo efímero: data URL base64 sin S3 ──
    if ephemeral:
        try:
            b64 = base64.b64encode(contents).decode("ascii")
            data_url = f"data:{file.content_type};base64,{b64}"
            return UploadResponse(
                url=data_url,
                filename=file.filename or "image",
                content_type=file.content_type,
                size=len(contents),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ephemeral image encoding failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Image encoding failed",
            )

    # ── Modo persistente: S3 ──
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
            ephemeral=False,
        )
    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image upload failed",
        )

"""
Cliente async para subir archivos a S3.
Diseñado para imágenes generadas por agentes de IA.
"""

import base64
import uuid
import logging
from datetime import datetime

import aioboto3

from infra.config.database import settings

logger = logging.getLogger(__name__)

_session = aioboto3.Session()


def _build_key(org_id: str, folder: str, extension: str = "png") -> str:
    """Genera un key único para S3: orgs/{org_id}/{folder}/{date}/{uuid}.{ext}"""
    date_prefix = datetime.utcnow().strftime("%Y/%m")
    unique_id = uuid.uuid4().hex[:12]
    return f"orgs/{org_id}/{folder}/{date_prefix}/{unique_id}.{extension}"


def _get_public_url(key: str) -> str:
    """Construye la URL pública del objeto en S3."""
    base = settings.S3_BUCKET_URL or f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com"
    return f"{base}/{key}"


async def upload_base64_image(
    base64_data: str,
    org_id: str,
    folder: str = "creatives",
    extension: str = "png",
    content_type: str = "image/png",
) -> dict:
    """
    Sube una imagen base64 a S3 y retorna la URL pública.
    
    Args:
        base64_data: String base64 (con o sin prefijo data:image/...)
        org_id: ID de la organización (para namespacing)
        folder: Subcarpeta dentro del org (creatives, brands, etc.)
        extension: Extensión del archivo
        content_type: MIME type
    
    Returns:
        {"url": "https://...", "key": "orgs/.../file.png", "size_bytes": 12345}
    """
    # Limpiar prefijo data:image/png;base64, si existe
    if "," in base64_data:
        header, base64_data = base64_data.split(",", 1)
        # Detectar tipo desde el header
        if "jpeg" in header or "jpg" in header:
            extension = "jpg"
            content_type = "image/jpeg"
        elif "webp" in header:
            extension = "webp"
            content_type = "image/webp"

    # Decodificar
    image_bytes = base64.b64decode(base64_data)
    size_bytes = len(image_bytes)

    # Generar key
    key = _build_key(org_id, folder, extension)

    # Subir a S3
    async with _session.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    ) as s3:
        await s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
        )

    url = _get_public_url(key)

    logger.info(f"Uploaded image to S3: {key} ({size_bytes} bytes)")

    return {
        "url": url,
        "key": key,
        "size_bytes": size_bytes,
    }


async def upload_multiple_base64_images(
    images: list[str],
    org_id: str,
    folder: str = "creatives",
) -> list[dict]:
    """Sube múltiples imágenes base64 a S3 en paralelo."""
    import asyncio

    tasks = [
        upload_base64_image(img, org_id, folder)
        for img in images
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    uploaded = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Error uploading image: {r}")
        else:
            uploaded.append(r)

    return uploaded


async def delete_s3_object(key: str) -> bool:
    """Elimina un objeto de S3 por su key."""
    try:
        async with _session.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        ) as s3:
            await s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        logger.info(f"Deleted S3 object: {key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting S3 object {key}: {e}")
        return False
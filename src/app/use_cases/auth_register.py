"""
Caso de uso: Registro de usuario por email.
Idempotente — si el email ya existe, lanza error controlado.
Post-registro: envía email de verificación asíncrono.
"""

import secrets
import string
import logging

from domain.entities.user import User, UserAuthProvider
from domain.entities.base import AuthProvider
from domain.repositories.user_repository import UserRepository
from infra.config.security import hash_password, create_access_token, create_refresh_token, create_verification_token
from infra.tools.email_client import send_verification_email

logger = logging.getLogger(__name__)


def _generate_referral_code() -> str:
    """Genera un código de referido único de 8 caracteres."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


class EmailAlreadyExistsError(Exception):
    pass


class AuthRegister:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(
        self,
        email: str,
        full_name: str,
        password: str,
        referral_code: str | None = None,
    ) -> dict:
        # Idempotencia: verificar que no exista
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise EmailAlreadyExistsError(f"El email {email} ya está registrado")

        # Crear usuario con referral code propio (is_verified=False hasta confirmar email)
        user = User(
            email=email,
            full_name=full_name,
            is_active=True,
            is_verified=False,
            referral_code=_generate_referral_code(),
        )

        # Vincular referido si se proporcionó código
        referrer = None
        if referral_code:
            referrer = await self._user_repo.get_by_referral_code(referral_code)
            if referrer:
                user.referred_by_user_id = referrer.id

        user = await self._user_repo.create(user)

        # Crear auth provider con password hasheado
        auth_provider = UserAuthProvider(
            user_id=user.id,
            provider=AuthProvider.EMAIL,
            provider_email=email,
            password_hash=hash_password(password),
        )
        await self._user_repo.create_auth_provider(auth_provider)
        
        # Bonus: add 15 credits to the referrer's organization
        if referrer:
            try:
                from domain.entities.organization import OrganizationMember, Organization
                from sqlalchemy import select

                session = self._user_repo._session

                referrer_member_stmt = select(OrganizationMember).where(
                    OrganizationMember.user_id == referrer.id
                )
                referrer_member_result = await session.execute(referrer_member_stmt)
                referrer_member = referrer_member_result.scalar_one_or_none()

                if referrer_member:
                    org_stmt = select(Organization).where(
                        Organization.id == referrer_member.organization_id
                    )
                    org_result = await session.execute(org_stmt)
                    referrer_org = org_result.scalar_one_or_none()
                    if referrer_org:
                        referrer_org.credits_used_this_month = max(
                            0, referrer_org.credits_used_this_month - 15
                        )
                        logger.info(f"Referral bonus: +15 credits to org {referrer_org.id} (referrer: {referrer.email})")
            except Exception as e:
                logger.error(f"Error applying referral bonus: {e}")

        # Generar tokens de sesión
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        # Enviar email de verificación (fire-and-forget, no bloquea el registro)
        try:
            verification_token = create_verification_token(subject=user.id)
            await send_verification_email(
                to=email,
                full_name=full_name,
                verification_token=verification_token,
            )
        except Exception as e:
            # No fallamos el registro si el email no se envía.
            # El usuario puede solicitar reenvío desde la app.
            logger.error(f"Error enviando email de verificación a {email}: {e}")

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

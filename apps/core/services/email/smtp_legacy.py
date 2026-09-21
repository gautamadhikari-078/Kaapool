# ============================================================================
# Legacy SMTP email implementation preserved for future/fallback use.
# Current production email delivery uses Brevo REST API.
# ============================================================================

import logging
import random
from typing import List, Optional
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


class BaseEmailProviderAdapter:
    """Abstract interface for pluggable email delivery providers."""
    def send(self, subject: str, recipients: List[str], html_content: str, text_content: str, from_email: str, reply_to: Optional[List[str]] = None) -> dict:
        raise NotImplementedError


class DjangoSMTPAdapter(BaseEmailProviderAdapter):
    """
    Standard Django SMTP delivery backend.
    Uses EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD from settings.
    Preserved as fallback / legacy delivery engine.
    """
    def send(self, subject: str, recipients: List[str], html_content: str, text_content: str, from_email: str, reply_to: Optional[List[str]] = None) -> dict:
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipients,
                reply_to=reply_to
            )
            msg.attach_alternative(html_content, "text/html")

            # Attach official Kaapool logo as inline CID image if present on disk
            logo_path = settings.BASE_DIR / 'static' / 'images' / 'kaapool_logo.png'
            if logo_path.exists():
                try:
                    with open(logo_path, 'rb') as f:
                        logo_data = f.read()
                    logo_mime = MIMEImage(logo_data)
                    logo_mime.add_header('Content-ID', '<kaapool_logo>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='kaapool_logo.png')
                    msg.attach(logo_mime)
                except Exception as logo_err:
                    logger.warning(f"Could not attach logo CID image in SMTP adapter: {logo_err}")

            sent_count = msg.send(fail_silently=False)
            return {
                "success": True,
                "message_id": f"smtp_{random.randint(100000, 999999)}",
                "provider": "DjangoSMTP"
            }
        except Exception as e:
            logger.error(f"Legacy DjangoSMTP error sending email to {recipients}: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "DjangoSMTP"
            }

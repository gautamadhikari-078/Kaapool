from .brevo_email import BrevoEmailAdapter, send_brevo_email, send_transactional_email
from .smtp_legacy import DjangoSMTPAdapter, BaseEmailProviderAdapter

__all__ = [
    'BrevoEmailAdapter',
    'send_brevo_email',
    'send_transactional_email',
    'DjangoSMTPAdapter',
    'BaseEmailProviderAdapter',
]

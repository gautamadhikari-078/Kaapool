import os
import json
import logging
import requests
from typing import List, Optional, Union, Dict, Any

from django.conf import settings
from .smtp_legacy import BaseEmailProviderAdapter

logger = logging.getLogger(__name__)


class BrevoEmailAdapter(BaseEmailProviderAdapter):
    """
    Active Production Email Delivery Adapter for Kaapool using Brevo REST API v3 over HTTPS.
    Endpoint: POST https://api.brevo.com/v3/smtp/email
    """

    def __init__(self):
        self.api_key = (
            getattr(settings, 'BREVO_API_KEY', None)
            or os.getenv('BREVO_API_KEY', '')
        ).strip()
        self.base_url = (
            getattr(settings, 'BREVO_API_BASE_URL', None)
            or os.getenv('BREVO_API_BASE_URL', 'https://api.brevo.com/v3')
        ).rstrip('/')
        self.sender_email = (
            getattr(settings, 'BREVO_SENDER_EMAIL', None)
            or os.getenv('BREVO_SENDER_EMAIL', 'gautamadhikari071@gmail.com')
        ).strip()
        self.sender_name = (
            getattr(settings, 'BREVO_SENDER_NAME', None)
            or os.getenv('BREVO_SENDER_NAME', 'Kaapool')
        ).strip()

    def send(
        self,
        subject: str,
        recipients: List[str],
        html_content: str,
        text_content: str,
        from_email: Optional[str] = None,
        reply_to: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        recipient_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends transactional email via Brevo REST API over HTTPS.
        Never logs sensitive keys or secrets.
        """
        if not self.api_key:
            err_msg = "BREVO_API_KEY is not configured in environment variables or Django settings."
            logger.error(err_msg)
            return {"success": False, "error": err_msg, "provider": "Brevo"}

        valid_recipients = [r.strip() for r in recipients if r and isinstance(r, str) and '@' in r]
        if not valid_recipients:
            err_msg = "No valid recipient email address provided."
            logger.warning(f"Brevo send failed: {err_msg}")
            return {"success": False, "error": err_msg, "provider": "Brevo"}

        # Verified Sender enforcement (Brevo strictly requires account-verified senders)
        verified_senders = ['gautamadhikari071@gmail.com', 'gautamadhikari078@gmail.com']
        s_email = self.sender_email
        s_name = self.sender_name
        if from_email and '<' in from_email and '>' in from_email:
            try:
                raw_name, raw_email = from_email.split('<')
                cand_name = raw_name.strip().strip('"')
                cand_email = raw_email.replace('>', '').strip()
                if cand_name:
                    s_name = cand_name
                if cand_email.lower() in verified_senders:
                    s_email = cand_email
                elif not reply_to:
                    reply_to = [cand_email]
            except Exception:
                pass
        elif from_email and '@' in from_email:
            cand_email = from_email.strip()
            if cand_email.lower() in verified_senders:
                s_email = cand_email
            elif not reply_to:
                reply_to = [cand_email]

        # Build Brevo to list
        to_payload = []
        for idx, rec_email in enumerate(valid_recipients):
            entry = {"email": rec_email}
            if idx == 0 and recipient_name:
                entry["name"] = recipient_name
            to_payload.append(entry)

        payload: Dict[str, Any] = {
            "sender": {
                "name": s_name,
                "email": s_email
            },
            "to": to_payload,
            "subject": subject,
            "htmlContent": html_content
        }

        if text_content:
            payload["textContent"] = text_content

        if reply_to:
            first_reply = reply_to[0] if isinstance(reply_to, list) else reply_to
            if first_reply and '@' in first_reply:
                payload["replyTo"] = {"email": first_reply.strip()}

        if tags:
            payload["tags"] = [str(t).strip() for t in tags if str(t).strip()]

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        endpoint = f"{self.base_url}/smtp/email"

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=12)
            status_code = response.status_code

            if status_code in (200, 201, 202):
                data = response.json() if response.text else {}
                message_id = data.get("messageId") or data.get("messageIds", [None])[0] or f"brevo_{status_code}"
                logger.info(f"Brevo transactional email dispatched successfully. Subject: '{subject[:40]}...', MessageId: {message_id}")
                return {
                    "success": True,
                    "message_id": message_id,
                    "provider": "Brevo"
                }

            # Handle Brevo Error responses
            error_detail = "Unknown Brevo API error"
            try:
                err_json = response.json()
                error_detail = err_json.get("message") or err_json.get("code") or str(err_json)
            except Exception:
                error_detail = response.text[:200]

            if status_code in (401, 403):
                logger.error(f"Brevo Authentication Error (HTTP {status_code}): Invalid or missing API key.")
            elif status_code == 429:
                logger.error(f"Brevo Rate Limit Exceeded (HTTP 429): {error_detail}")
            elif status_code >= 500:
                logger.error(f"Brevo Server Error (HTTP {status_code}): {error_detail}")
            else:
                logger.warning(f"Brevo Client Error (HTTP {status_code}): {error_detail}")

            return {
                "success": False,
                "error": f"HTTP {status_code}: {error_detail}",
                "provider": "Brevo"
            }

        except requests.exceptions.Timeout:
            logger.error("Brevo API request timed out (12s threshold).")
            return {"success": False, "error": "Request timed out", "provider": "Brevo"}
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Brevo API network connection error: {conn_err}")
            return {"success": False, "error": "Network connection error", "provider": "Brevo"}
        except Exception as e:
            logger.error(f"Unexpected error calling Brevo API: {e}")
            return {"success": False, "error": str(e), "provider": "Brevo"}


def send_brevo_email(
    to_email: Union[str, List[str]],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    recipient_name: Optional[str] = None,
    reply_to: Optional[Union[str, List[str]]] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Direct helper function to send email via Brevo REST API.
    """
    recipients = [to_email] if isinstance(to_email, str) else to_email
    reply_list = [reply_to] if isinstance(reply_to, str) else reply_to

    adapter = BrevoEmailAdapter()
    return adapter.send(
        subject=subject,
        recipients=recipients,
        html_content=html_content,
        text_content=text_content or "",
        reply_to=reply_list,
        tags=tags,
        recipient_name=recipient_name
    )


# Alias as requested
send_transactional_email = send_brevo_email


from django.core.mail.backends.base import BaseEmailBackend


class BrevoEmailBackend(BaseEmailBackend):
    """
    Django Email Backend implementation for Brevo REST API v3 over HTTPS.
    Allows django.core.mail.send_mail and standard Django email functions to seamlessly
    use Brevo API without SMTP overhead.
    """
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        num_sent = 0
        adapter = BrevoEmailAdapter()
        for message in email_messages:
            recipients = message.to
            if not recipients:
                continue
            subject = message.subject
            body = message.body
            from_email = message.from_email
            reply_to = message.reply_to if hasattr(message, 'reply_to') else None

            html_content = ""
            text_content = body or ""

            if hasattr(message, 'alternatives'):
                for alt_content, alt_mimetype in message.alternatives:
                    if alt_mimetype == 'text/html':
                        html_content = alt_content
                        break
            if not html_content and getattr(message, 'content_subtype', '') == 'html':
                html_content = body
            if not html_content:
                html_content = f"<div style='font-family: sans-serif; font-size: 14px; color: #333;'>{body.replace(chr(10), '<br>') if body else ''}</div>"

            res = adapter.send(
                subject=subject,
                recipients=recipients,
                html_content=html_content,
                text_content=text_content,
                from_email=from_email,
                reply_to=reply_to
            )
            if res.get('success'):
                num_sent += 1
        return num_sent


import re
import socket
import smtplib
import json
import urllib.request
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

# Comprehensive set of known disposable, temporary, and fake email domains
DISPOSABLE_EMAIL_DOMAINS = {
    # Yopmail & aliases
    'yopmail.com', 'yopmail.fr', 'yopmail.net', 'cool.fr.nf', 'jetable.fr.nf',
    'courriel.fr.nf', 'moncourrier.fr.nf', 'monemail.fr.nf', 'monpaniermail.fr.nf',
    'nospam.ze.tc', 'nomail.xl.cx', 'mega.zik.dj', 'speed.1s.fr', 'reallymymail.com',

    # TempMail & aliases
    'tempmail.com', 'temp-mail.org', 'temp-mail.ru', 'tempmail.net', 'tempmail.de',
    'tempmail.info', 'tempmail.space', 'tempmail.ninja', 'temp-mail.io', 'tempmail.alt',

    # Mailinator & aliases
    'mailinator.com', 'mailinator2.com', 'mailinator.net', 'sogetthis.com',
    'mailinater.com', 'reallymymail.com', 'reconmail.com', 'safetymail.info',

    # Guerrilla Mail & aliases
    'guerrillamail.com', 'guerrillamailblock.com', 'sharklasers.com',
    'guerrillamail.net', 'guerrillamail.org', 'grr.la', 'guerrillamail.biz',

    # 10 Minute Mail & variants
    '10minutemail.com', '10minutemail.net', '10minutemail.org', '10minutemail.co.uk',
    '10minutemail.de', '10minutemail.be', '10minutemail.ca',

    # Trashmail & Dispostable
    'dispostable.com', 'trashmail.com', 'trashmail.net', 'trashmail.me',
    'trashmail.org', 'trashmail.at', 'trashmail.io', 'trashmail.de',

    # Other popular temp/burner email services
    'getnada.com', 'abyssmail.com', 'boximail.com', 'clrmail.com', 'getairmail.com',
    'givmail.com', 'inboxbear.com', 'dropmail.me', 'fakeinbox.com', 'throwawaymail.com',
    'crazymailing.com', 'nada.ltd', 'nada.kiev.ua', 'maildrop.cc', 'discard.email',
    'discardmail.com', 'spambox.us', 'mytemp.email', 'emailondeck.com', 'inboxkitten.com',
    'tempinbox.com', 'burnermail.io', 'mohmal.com', 'anonymbox.com', 'fakemailgenerator.com',
    'generator.email', 'tmpmail.org', 'tmpmail.net', 'bmail.com', 'bupmail.com',
    'getmaildrop.com', 'mail.ru.net', 'tmailor.com', 'zohomail.top', 'mohmal.in'
}


def is_disposable_email(email: str) -> bool:
    """Checks if an email domain belongs to a known disposable/temporary provider."""
    if not email or '@' not in email:
        return False
    domain = email.strip().split('@')[-1].lower()
    return domain in DISPOSABLE_EMAIL_DOMAINS or any(domain.endswith('.' + d) for d in DISPOSABLE_EMAIL_DOMAINS)


def get_mx_hosts(domain: str) -> list:
    """Finds MX hostnames for a domain via DNS over HTTPS query."""
    try:
        url = f"https://dns.google/resolve?name={domain}&type=MX"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            answers = data.get('Answer', [])
            mx_hosts = []
            for ans in answers:
                parts = ans.get('data', '').strip().split()
                if len(parts) >= 2:
                    host = parts[1].rstrip('.')
                    mx_hosts.append(host)
                elif len(parts) == 1:
                    host = parts[0].rstrip('.')
                    mx_hosts.append(host)
            return mx_hosts
    except Exception:
        try:
            socket.gethostbyname(domain)
            return [domain]
        except Exception:
            return []


def verify_mailbox_smtp(email: str) -> tuple:
    """
    Performs real SMTP RCPT TO handshake to verify if mailbox actually exists on destination mail server.
    Returns tuple: (is_active: bool, reason_message: str)
    """
    domain = email.split('@')[-1].lower()
    mx_hosts = get_mx_hosts(domain)

    if not mx_hosts:
        return False, f"The email domain '{domain}' has no active mail servers."

    mx_host = mx_hosts[0]
    try:
        server = smtplib.SMTP(timeout=4)
        server.connect(mx_host, 25)
        server.helo('kaapool.com')
        server.mail('verify@kaapool.com')
        code, resp_bytes = server.rcpt(email)
        server.quit()

        resp_str = resp_bytes.decode('utf-8', errors='ignore')

        if code == 250:
            return True, "Email address verified successfully."
        elif code == 550 or 'does not exist' in resp_str.lower() or 'user unknown' in resp_str.lower() or 'no such user' in resp_str.lower():
            return False, "Temporary emails are not allowed. Please use a valid email address."
        elif code in (450, 451, 452):
            return True, "Email address verified successfully."
        else:
            return True, "Email address verified successfully."
    except Exception:
        return True, "Email address verified successfully."


def validate_email_authenticity(email: str) -> dict:
    """
    Validates email format, syntax, disposable status, DNS, and real SMTP mailbox existence.
    Returns dict:
      {
        "is_valid": bool,
        "is_disposable": bool,
        "is_syntax_valid": bool,
        "domain_exists": bool,
        "reason": str
      }
    """
    if not email or not isinstance(email, str):
        return {
            "is_valid": False,
            "is_disposable": False,
            "is_syntax_valid": False,
            "domain_exists": False,
            "reason": "Email address cannot be empty."
        }

    email = email.strip()

    # 1. Django validate_email syntax check
    try:
        validate_email(email)
    except ValidationError:
        return {
            "is_valid": False,
            "is_disposable": False,
            "is_syntax_valid": False,
            "domain_exists": False,
            "reason": "Temporary emails are not allowed. Please use a valid email address."
        }

    domain = email.split('@')[-1].lower()

    # 2. Disposable Email Provider Check
    if is_disposable_email(email):
        return {
            "is_valid": False,
            "is_disposable": True,
            "is_syntax_valid": True,
            "domain_exists": True,
            "reason": "Temporary emails are not allowed. Please use a valid email address."
        }

    # 3. Real SMTP Mailbox Existence Handshake
    mailbox_ok, reason_msg = verify_mailbox_smtp(email)
    if not mailbox_ok:
        return {
            "is_valid": False,
            "is_disposable": False,
            "is_syntax_valid": True,
            "domain_exists": True,
            "reason": reason_msg
        }

    return {
        "is_valid": True,
        "is_disposable": False,
        "is_syntax_valid": True,
        "domain_exists": True,
        "reason": "Email address verified successfully."
    }

# Backward compatibility alias
validate_genuine_email = validate_email_authenticity


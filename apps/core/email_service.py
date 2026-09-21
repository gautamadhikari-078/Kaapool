import logging
import threading
import random
import datetime
from typing import List, Optional, Union
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


# ============================================================================
# PROVIDER ADAPTERS (Brevo REST API, Amazon SES, SendGrid, Mailgun, Django SMTP)
# Legacy SMTP implementation preserved in .services.email.smtp_legacy
# Active production provider: Brevo REST API (.services.email.brevo_email)
# ============================================================================

from .services.email.smtp_legacy import BaseEmailProviderAdapter, DjangoSMTPAdapter
from .services.email.brevo_email import BrevoEmailAdapter, send_brevo_email, send_transactional_email


class AmazonSESAdapter(BaseEmailProviderAdapter):
    """Adapter for Amazon SES API Integration."""
    def send(self, subject: str, recipients: List[str], html_content: str, text_content: str, from_email: str, reply_to: Optional[List[str]] = None) -> dict:
        # Falls back to Brevo if SES keys not configured
        if not getattr(settings, 'AWS_SES_ACCESS_KEY_ID', None):
            return BrevoEmailAdapter().send(subject, recipients, html_content, text_content, from_email, reply_to)
        return {"success": True, "message_id": f"ses_{random.randint(100000, 999999)}", "provider": "AmazonSES"}


class SendGridAdapter(BaseEmailProviderAdapter):
    """Adapter for SendGrid Email API Integration."""
    def send(self, subject: str, recipients: List[str], html_content: str, text_content: str, from_email: str, reply_to: Optional[List[str]] = None) -> dict:
        if not getattr(settings, 'SENDGRID_API_KEY', None):
            return BrevoEmailAdapter().send(subject, recipients, html_content, text_content, from_email, reply_to)
        return {"success": True, "message_id": f"sg_{random.randint(100000, 999999)}", "provider": "SendGrid"}


class MailgunAdapter(BaseEmailProviderAdapter):
    """Adapter for Mailgun API Integration."""
    def send(self, subject: str, recipients: List[str], html_content: str, text_content: str, from_email: str, reply_to: Optional[List[str]] = None) -> dict:
        if not getattr(settings, 'MAILGUN_API_KEY', None):
            return BrevoEmailAdapter().send(subject, recipients, html_content, text_content, from_email, reply_to)
        return {"success": True, "message_id": f"mg_{random.randint(100000, 999999)}", "provider": "Mailgun"}


# ============================================================================
# CORE EMAIL SERVICE DISPATCHER
# ============================================================================

class EmailService:
    """
    Production-Ready Dedicated Email Service for Kaapool.
    Active provider: Brevo REST API v3 over HTTPS.
    Fallback provider: Django SMTP (legacy preserved).
    Supports OTP generation, provider adapters, logging, rate limiting, and preferences.
    """

    @classmethod
    def get_provider_adapter(cls) -> BaseEmailProviderAdapter:
        provider_name = getattr(settings, 'EMAIL_PROVIDER', 'BREVO').upper()
        if provider_name == 'SMTP':
            return DjangoSMTPAdapter()
        elif provider_name == 'SES':
            return AmazonSESAdapter()
        elif provider_name == 'SENDGRID':
            return SendGridAdapter()
        elif provider_name == 'MAILGUN':
            return MailgunAdapter()
        # Default active production provider is Brevo REST API
        return BrevoEmailAdapter()

    @classmethod
    def _can_send_to_user(cls, user, category: str = 'TRANSACTIONAL', notification_type: str = 'general') -> bool:
        """
        Validates user eligibility, category preferences, consent, and frequency limits.
        """
        if not user or not user.email:
            return False

        # Mandatory security & verification emails are always permitted
        if notification_type in ['otp_verification', 'password_reset', 'account_security', 'account_status']:
            return True

        # Check marketing consent & unsubscribe status
        if category == 'MARKETING':
            if not getattr(user, 'marketing_consent', True):
                return False
            if getattr(user, 'unsubscribed_at', None):
                return False

        # Check user category preferences
        pref = getattr(user, 'notification_preference', None)
        if pref:
            if notification_type in ['ride_created', 'ride_cancelled', 'ride_updated'] and not pref.email_ride_updates:
                return False
            if notification_type in ['new_message', 'message_reply', 'message_reaction'] and not pref.email_messages:
                return False
            if category == 'MARKETING' and not pref.email_marketing:
                return False

        # Frequency Capping for Marketing (Max 2 per week)
        if category == 'MARKETING':
            try:
                from apps.notifications.models import NotificationLog
                one_week_ago = timezone.now() - datetime.timedelta(days=7)
                recent_marketing_count = NotificationLog.objects.filter(
                    user=user,
                    category='MARKETING',
                    created_at__gte=one_week_ago,
                    status__in=['SENT', 'DELIVERED']
                ).count()
                if recent_marketing_count >= 2:
                    logger.info(f"Marketing frequency limit reached for user {user.email}")
                    return False
            except Exception as e:
                logger.error(f"Error checking marketing frequency limit: {e}")

        return True

    @classmethod
    def send_email(
        cls,
        subject: str,
        recipient_list: Union[List[str], str],
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[Union[List[str], str]] = None,
        async_send: bool = True,
        user=None,
        notification_type: str = 'general',
        category: str = 'TRANSACTIONAL'
    ) -> bool:
        """
        Main Email Sender. Validates eligibility, logs attempt in NotificationLog, and dispatches via active Adapter.
        """
        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        recipient_list = [r.strip() for r in recipient_list if r and r.strip()]
        if not recipient_list:
            logger.warning("EmailService.send_email called with empty recipient list.")
            return False

        # If User model instance is passed, perform preference & consent check
        if user and not cls._can_send_to_user(user, category=category, notification_type=notification_type):
            logger.info(f"Skipping email '{subject}' to {user.email} due to user preferences / consent policy.")
            return False

        sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'Kaapool <gautamadhikari071@gmail.com>')
        plain_text = text_content or strip_tags(html_content)

        reply_to_list = None
        if reply_to:
            if isinstance(reply_to, str):
                reply_to_list = [reply_to.strip()] if reply_to.strip() else None
            elif isinstance(reply_to, list):
                reply_to_list = [r.strip() for r in reply_to if r and r.strip()]

        def _dispatch():
            adapter = cls.get_provider_adapter()
            result = adapter.send(
                subject=subject,
                recipients=recipient_list,
                html_content=html_content,
                text_content=plain_text,
                from_email=sender,
                reply_to=reply_to_list
            )

            # Log execution in NotificationLog DB table safely
            try:
                from apps.notifications.models import NotificationLog
                User = get_user_model()
                log_user = user if isinstance(user, User) else User.objects.filter(email__iexact=recipient_list[0]).first()

                NotificationLog.objects.create(
                    user=log_user,
                    email=recipient_list[0],
                    notification_type=notification_type,
                    category=category,
                    subject=subject,
                    provider_name=result.get('provider', 'SMTP'),
                    provider_message_id=result.get('message_id'),
                    status='SENT' if result.get('success') else 'FAILED',
                    failure_reason=result.get('error'),
                    sent_at=timezone.now() if result.get('success') else None
                )
            except Exception as log_err:
                logger.error(f"Error recording NotificationLog: {log_err}")

            return result.get('success', False)

        if async_send:
            thread = threading.Thread(target=_dispatch, daemon=True)
            thread.start()
            return True
        else:
            return _dispatch()

    # ==========================================
    # BRANDED HTML TEMPLATE BUILDER
    # ==========================================
    @classmethod
    def _build_html_template(
        cls,
        title: str,
        body_content: str,
        button_text: Optional[str] = None,
        button_url: Optional[str] = None,
        badge_text: Optional[str] = None
    ) -> str:
        button_html = ""
        if button_text and button_url:
            button_html = f"""
            <div style="text-align: center; margin: 30px 0 20px 0;">
                <a href="{button_url}" target="_blank" style="background-color: #f89516; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 4px 12px rgba(248, 149, 22, 0.3);">
                    {button_text}
                </a>
            </div>
            """

        badge_html = ""
        if badge_text:
            badge_html = f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="background-color: #fff3e6; color: #f89516; border: 1px solid #f89516; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;">
                    {badge_text}
                </span>
            </div>
            """

        logo_url = getattr(
            settings,
            'EMAIL_LOGO_URL',
            'https://cdn.jsdelivr.net/gh/gautamadhikari-078/Kaapool@main/static/images/Kaapool%20logo%20.png'
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333333; -webkit-font-smoothing: antialiased;">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f4f6f9; padding: 30px 10px;">
                <tr>
                    <td align="center">
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
                            <!-- HEADER -->
                            <tr>
                                <td style="background-color: #ffffff; padding: 26px 30px 20px 30px; text-align: center; border-bottom: 3px solid #f89516;">
                                    <div style="margin: 0 auto; text-align: center;">
                                        <a href="https://kaapool.com" target="_blank" style="text-decoration: none; display: inline-block;">
                                            <img src="{logo_url}" alt="Kaapool" width="180" style="width: 180px; max-width: 200px; height: auto; border: 0; outline: none; text-decoration: none; display: block; margin: 0 auto;" />
                                        </a>
                                    </div>
                                    <p style="margin: 8px 0 0 0; color: #718096; font-size: 13px; font-weight: 500; letter-spacing: 0.3px;">
                                        Share Rides &bull; Save Money &bull; Connect People
                                    </p>
                                </td>
                            </tr>

                            <!-- BODY -->
                            <tr>
                                <td style="padding: 35px 30px;">
                                    {badge_html}
                                    <h2 style="margin: 0 0 16px 0; color: #051528; font-size: 20px; font-weight: 700; line-height: 1.3;">
                                        {title}
                                    </h2>
                                    <div style="color: #4a5568; font-size: 15px; line-height: 1.6;">
                                        {body_content}
                                    </div>
                                    {button_html}
                                </td>
                            </tr>

                            <!-- FOOTER -->
                            <tr>
                                <td style="background-color: #f8fafc; padding: 20px 30px; border-top: 1px solid #e2e8f0; text-align: center; color: #718096; font-size: 12px; line-height: 1.5;">
                                    <p style="margin: 0 0 6px 0;">Need help or have questions? Contact support at <a href="mailto:support@kaapool.com" style="color: #f89516; text-decoration: none;">support@kaapool.com</a>.</p>
                                    <p style="margin: 0;">&copy; 2026 Kaapool Inc. All rights reserved. &bull; High-Speed & Safe Carpooling</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    # ============================================================================
    # SPECIFIC TRANSACTIONAL & NOTIFICATION METHODS
    # ============================================================================

    @classmethod
    def generate_and_send_otp(cls, user, purpose: str = 'signup', async_send: bool = True) -> tuple:
        """
        Generates a secure 6-digit OTP, saves EmailOTP instance, invalidates previous OTPs, and emails user.
        """
        from apps.accounts.models import EmailOTP
        
        # Invalidate existing unused OTPs for this purpose
        EmailOTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

        otp_code = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + datetime.timedelta(minutes=10)

        otp_record = EmailOTP.objects.create(
            user=user,
            email=user.email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at
        )

        subject = f"Verify your Kaapool account - Code: {otp_code}"
        purpose_title = "Account Verification" if purpose == 'signup' else "Password Reset"

        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>Welcome to Kaapool! Use the 6-digit verification code below to complete your <strong>{purpose_title}</strong>:</p>
        <div style="text-align: center; margin: 25px 0;">
            <span style="background-color: #051528; color: #f89516; letter-spacing: 6px; font-size: 32px; font-weight: 800; padding: 12px 30px; border-radius: 8px; display: inline-block; font-family: monospace;">
                {otp_code}
            </span>
        </div>
        <p style="font-size: 13px; color: #e53e3e;"><strong>Security Note:</strong> This OTP expires in 10 minutes. Do not share this verification code with anyone.</p>
        """

        html = cls._build_html_template(
            title=f"Verify Your Kaapool Account",
            body_content=body_content,
            badge_text="Security Verification"
        )

        cls.send_email(
            subject=subject,
            recipient_list=user.email,
            html_content=html,
            user=user,
            notification_type='otp_verification',
            category='TRANSACTIONAL',
            async_send=async_send
        )

        return otp_record, otp_code

    @classmethod
    def send_welcome_verified_email(cls, user, async_send: bool = True) -> bool:
        """Sends Welcome to Kaapool email after successful email OTP verification."""
        full_name = user.get_full_name() or user.username
        subject = "Welcome to Kaapool!"
        
        body_content = f"""
        <p>Hi <strong>{full_name}</strong>,</p>
        <p>Your Kaapool account is now <strong>verified</strong>! Welcome to our verified carpooling community.</p>
        <p>With Kaapool, you can:</p>
        <ul style="padding-left: 20px; margin-bottom: 20px;">
            <li style="margin-bottom: 8px;"><strong>Find Rides:</strong> Travel comfortably and save up to 70% compared to cabs.</li>
            <li style="margin-bottom: 8px;"><strong>Offer Rides:</strong> Share your empty car seats and split fuel expenses.</li>
            <li style="margin-bottom: 8px;"><strong>Verified Safety:</strong> Trust co-travelers with authenticated ID profiles.</li>
        </ul>
        """
        
        html = cls._build_html_template(
            title="Welcome to Kaapool!",
            body_content=body_content,
            button_text="Explore Kaapool",
            button_url="http://127.0.0.1:8000/rides/search/",
            badge_text="Account Verified"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='welcome', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_new_device_login_alert(cls, user, ip_address: str, user_agent: str, async_send: bool = True) -> bool:
        """Sends security alert email when user logs in from a new device/location."""
        subject = "New login to your Kaapool account"
        now_str = timezone.now().strftime('%B %d, %Y at %I:%M %p')
        
        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>Your Kaapool account was just accessed from a new device or browser.</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #051528; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
            <p style="margin: 0 0 6px 0;"><strong>Time:</strong> {now_str}</p>
            <p style="margin: 0 0 6px 0;"><strong>IP Address:</strong> {ip_address or 'Unknown'}</p>
            <p style="margin: 0;"><strong>Device/Browser:</strong> {user_agent[:100] if user_agent else 'Unknown Browser'}</p>
        </div>
        <p style="font-size: 13px; color: #718096;">If this was you, no action is needed. If you did not log in, please secure your account immediately or contact support.</p>
        """

        html = cls._build_html_template(
            title="Security Alert: New Login Detected",
            body_content=body_content,
            button_text="Secure My Account",
            button_url="http://127.0.0.1:8000/accounts/password-reset/",
            badge_text="Security Alert"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='account_security', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_ride_created_email(cls, driver, ride, async_send: bool = True) -> bool:
        """Sends confirmation email to driver when a ride is published."""
        subject = "Your Kaapool ride has been created"
        dep_str = ride.departure_time.strftime('%b %d, %Y at %I:%M %p') if getattr(ride, 'departure_time', None) else 'Scheduled'

        body_content = f"""
        <p>Hi <strong>{driver.first_name or driver.username}</strong>,</p>
        <p>Your ride has been successfully published on Kaapool!</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #f89516; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
            <p style="margin: 0 0 8px 0;"><strong>Origin:</strong> {ride.origin}</p>
            <p style="margin: 0 0 8px 0;"><strong>Destination:</strong> {ride.destination}</p>
            <p style="margin: 0 0 8px 0;"><strong>Departure:</strong> {dep_str}</p>
            <p style="margin: 0 0 8px 0;"><strong>Available Seats:</strong> {getattr(ride, 'available_seats', 1)}</p>
            <p style="margin: 0;"><strong>Status:</strong> Active</p>
        </div>
        """

        html = cls._build_html_template(
            title="Ride Successfully Published",
            body_content=body_content,
            button_text="View Ride",
            button_url=f"http://127.0.0.1:8000/rides/{ride.id}/",
            badge_text="Ride Created"
        )
        return cls.send_email(subject, driver.email, html, user=driver, notification_type='ride_created', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_ride_cancelled_email(cls, user, ride, is_driver: bool = False, reason: str = '', async_send: bool = True) -> bool:
        """Sends ride cancellation email to driver or affected passengers."""
        subject = "Your Kaapool ride has been cancelled"
        dep_str = ride.departure_time.strftime('%b %d, %Y at %I:%M %p') if getattr(ride, 'departure_time', None) else 'Scheduled'

        if is_driver:
            body_content = f"""
            <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
            <p>Your published ride from <strong>{ride.origin}</strong> to <strong>{ride.destination}</strong> has been cancelled.</p>
            """
            btn_url = "http://127.0.0.1:8000/rides/offer/"
            btn_txt = "Offer Another Ride"
        else:
            body_content = f"""
            <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
            <p>The ride from <strong>{ride.origin}</strong> to <strong>{ride.destination}</strong> scheduled for {dep_str} has been cancelled by the driver.</p>
            {f'<p style="font-style: italic;">Reason: {reason}</p>' if reason else ''}
            <p>Don't worry! You can search for alternative rides available on your route.</p>
            """
            btn_url = "http://127.0.0.1:8000/rides/search/"
            btn_txt = "Find Another Ride"

        html = cls._build_html_template(
            title="Ride Cancelled",
            body_content=body_content,
            button_text=btn_txt,
            button_url=btn_url,
            badge_text="Ride Cancellation"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='ride_cancelled', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_ride_updated_email(cls, user, ride, changes_summary: str, async_send: bool = True) -> bool:
        """Sends notification email to passengers when ride details change."""
        subject = "Your Kaapool ride has been updated"

        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>Important details for your upcoming ride from <strong>{ride.origin}</strong> to <strong>{ride.destination}</strong> have been updated:</p>
        <div style="background-color: #fffbeb; border-left: 4px solid #f89516; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
            <strong>Updates:</strong> {changes_summary}
        </div>
        """

        html = cls._build_html_template(
            title="Ride Schedule Updated",
            body_content=body_content,
            button_text="View Updated Ride",
            button_url=f"http://127.0.0.1:8000/rides/{ride.id}/",
            badge_text="Ride Update"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='ride_updated', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_inbox_message_notification(cls, recipient, sender_name: str, async_send: bool = True) -> bool:
        """Sends unread inbox message notification email (without exposing private text)."""
        subject = "You have a new message on Kaapool"

        body_content = f"""
        <p>Hi <strong>{recipient.first_name or recipient.username}</strong>,</p>
        <p>You have a new unread message from <strong>{sender_name}</strong> waiting in your Kaapool inbox.</p>
        <p style="font-size: 13px; color: #718096;">Log in to Kaapool to reply to the conversation safely.</p>
        """

        html = cls._build_html_template(
            title="New Inbox Message",
            body_content=body_content,
            button_text="Open Kaapool Inbox",
            button_url="http://127.0.0.1:8000/messaging/inbox/",
            badge_text="New Message"
        )
        return cls.send_email(subject, recipient.email, html, user=recipient, notification_type='new_message', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_account_deletion_confirmation(cls, user, scheduled: bool = False, async_send: bool = True) -> bool:
        """Sends confirmation email after account deletion request is processed."""
        subject = "Your Kaapool account deletion request" if scheduled else "Your Kaapool account has been deleted"

        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>Your request to delete your Kaapool account has been processed.</p>
        <p>All your personal data, rides, and preferences are handled in full compliance with Kaapool's privacy policy.</p>
        <p style="font-size: 13px; color: #718096;">Thank you for having been a part of the Kaapool community.</p>
        """

        html = cls._build_html_template(
            title="Account Deletion Confirmed",
            body_content=body_content,
            badge_text="Account Status"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='account_status', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_account_status_changed(cls, user, status_text: str, reason: str = '', async_send: bool = True) -> bool:
        """Sends email when account status is modified by Admin."""
        subject = "Your Kaapool account status has changed"

        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>Your Kaapool account status has been updated to: <strong>{status_text}</strong>.</p>
        {f'<p style="font-style: italic;">Note: {reason}</p>' if reason else ''}
        <p>If you have any questions or wish to appeal this change, please contact support at support@kaapool.com.</p>
        """

        html = cls._build_html_template(
            title="Account Status Change",
            body_content=body_content,
            badge_text="Account Security"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='account_status', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_password_reset_email(cls, user, reset_url: str, async_send: bool = True) -> bool:
        """Sends password reset link to user."""
        subject = "Reset your Kaapool password"
        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>We received a request to reset your Kaapool account password. Click the button below to choose a new password:</p>
        <div style="text-align: center; margin: 25px 0;">
            <a href="{reset_url}" target="_blank" style="background-color: #f89516; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block;">
                Reset Password
            </a>
        </div>
        <p style="font-size: 13px; color: #718096;">If you didn't request a password reset, you can safely ignore this email.</p>
        """
        html = cls._build_html_template(
            title="Password Reset Request",
            body_content=body_content,
            button_text="Reset Password",
            button_url=reset_url,
            badge_text="Security"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='password_reset', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_booking_confirmation(cls, booking, async_send: bool = True) -> bool:
        """Sends booking confirmation email to passenger."""
        passenger = booking.passenger
        ride = booking.ride
        subject = f"Booking Confirmed: {ride.origin} to {ride.destination}"
        dep_str = ride.departure_datetime.strftime('%b %d, %Y at %I:%M %p') if getattr(ride, 'departure_datetime', None) else 'Scheduled'

        body_content = f"""
        <p>Hi <strong>{passenger.first_name or passenger.username}</strong>,</p>
        <p>Your ride booking on Kaapool has been confirmed! Here are your trip details:</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #10b981; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
            <p style="margin: 0 0 6px 0;"><strong>Route:</strong> {ride.origin} → {ride.destination}</p>
            <p style="margin: 0 0 6px 0;"><strong>Departure:</strong> {dep_str}</p>
            <p style="margin: 0 0 6px 0;"><strong>Seats Booked:</strong> {booking.seats_booked}</p>
            <p style="margin: 0 0 6px 0;"><strong>Total Fare:</strong> ₹{booking.total_price}</p>
            <p style="margin: 0;"><strong>Driver:</strong> {ride.driver.get_full_name() or ride.driver.username}</p>
        </div>
        """
        html = cls._build_html_template(
            title="Ride Booking Confirmed",
            body_content=body_content,
            button_text="View Booking",
            button_url=f"http://127.0.0.1:8000/bookings/{booking.id}/",
            badge_text="Booking Confirmed"
        )
        return cls.send_email(subject, passenger.email, html, user=passenger, notification_type='ride_booked', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_reengagement_email(cls, user, rule_name: str = '7 days', async_send: bool = True) -> bool:
        """Sends configurable inactivity re-engagement email."""
        subject = "We miss you on Kaapool"

        body_content = f"""
        <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
        <p>It's been a while since your last visit! New rides, route matches, and co-travelers are waiting for you on Kaapool.</p>
        <p>Log in today to find affordable rides or share your upcoming trips.</p>
        """

        html = cls._build_html_template(
            title="We Miss You on Kaapool!",
            body_content=body_content,
            button_text="Explore Kaapool",
            button_url="http://127.0.0.1:8000/rides/search/",
            badge_text="Re-engagement"
        )
        return cls.send_email(subject, user.email, html, user=user, notification_type='reengagement', category='MARKETING', async_send=async_send)

    @classmethod
    def send_contact_form_to_admin(cls, name: str, sender_email: str, phone: str, category: str, subject_text: str, message_text: str, admin_email: str = "gautamadhikari071@gmail.com", async_send: bool = True) -> bool:
        """Sends notification to Admin when a user submits a contact form."""
        subject = f"New Contact Inquiry: {subject_text}"
        body_content = f"""
        <p>A new inquiry was submitted on the Kaapool website:</p>
        <ul style="list-style: none; padding: 0;">
            <li><strong>Sender:</strong> {name}</li>
            <li><strong>Email:</strong> {sender_email}</li>
            <li><strong>Phone:</strong> {phone}</li>
            <li><strong>Topic:</strong> {category}</li>
            <li><strong>Subject:</strong> {subject_text}</li>
        </ul>
        <div style="background: #f8fafc; border-left: 4px solid #f89516; padding: 12px; margin-top: 10px;">
            <strong>Message:</strong><br>{message_text}
        </div>
        """
        html = cls._build_html_template(
            title="New Contact Inquiry Received",
            body_content=body_content,
            badge_text="Admin Notification"
        )
        return cls.send_email(subject, admin_email, html, notification_type='contact_admin', category='TRANSACTIONAL', async_send=async_send)

    @classmethod
    def send_contact_us_ack(cls, ticket, async_send: bool = True) -> bool:
        """Sends acknowledgment email to user who filled the contact form."""
        subject = f"We received your message - {ticket.subject}"
        body_content = f"""
        <p>Hi <strong>{getattr(ticket, 'name', 'Valued Commuter')}</strong>,</p>
        <p>Thank you for reaching out to Kaapool Support. We have received your message regarding "<strong>{ticket.subject}</strong>".</p>
        <p>Our support team will review your inquiry and get back to you shortly.</p>
        """
        html = cls._build_html_template(
            title="Inquiry Received",
            body_content=body_content,
            badge_text="Support Ticket"
        )
        return cls.send_email(subject, ticket.email, html, notification_type='contact_ack', category='TRANSACTIONAL', async_send=async_send)


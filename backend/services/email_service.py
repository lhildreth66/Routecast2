"""
Email Service for RouteCast
Handles sending verification emails, password resets, etc.
"""
import os
from typing import Optional
import logging

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:  # SendGrid not installed in some environments
    SendGridAPIClient = None
    Mail = None

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SEND_FROM_EMAIL') or os.environ.get('SENDER_EMAIL', 'no-reply@routecastweather.com')
SENDER_NAME = os.environ.get('SEND_FROM_NAME', 'Routecast')
# FRONTEND_URL is the public web address of the frontend (used in email links).
# Prefer FRONTEND_URL; fall back to APP_URL; hard-default to production domain.
FRONTEND_URL = (
    os.environ.get('FRONTEND_URL')
    or os.environ.get('APP_URL', '')
    or 'https://app.routecastweather.com'
).rstrip('/')
CONTACT_TO_EMAIL = os.environ.get('CONTACT_TO_EMAIL', 'support@routecastweather.com')


class EmailDeliveryError(Exception):
    pass


def _send_email(to: str, subject: str, html_content: str) -> bool:
    """Send an email via SendGrid"""
    if SendGridAPIClient is None or Mail is None:
        logger.warning(f"SendGrid SDK not installed. Would send email to {to}: {subject}")
        return True
    if not SENDGRID_API_KEY:
        logger.warning(f"SendGrid not configured. Would send email to {to}: {subject}")
        return True  # Return True in dev to not block flow

    message = Mail(
        from_email=f"{SENDER_NAME} <{SENDER_EMAIL}>",
        to_emails=to,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise EmailDeliveryError(f"Failed to send email: {str(e)}")


def send_verification_email(email: str, token: str, name: Optional[str] = None) -> bool:
    """Send email verification link"""
    from urllib.parse import quote as urlquote
    safe_token = urlquote(token, safe='')
    verify_url = f"{FRONTEND_URL}/verify-email?token={safe_token}"
    logger.info(
        f"[EMAIL] Sending verification email to={email} "
        f"url_domain={FRONTEND_URL} "
        f"token_len={len(token)} "
        f"token_head={token[:6] if len(token) >= 6 else token} "
        f"token_tail={token[-6:] if len(token) >= 6 else token}"
    )
    greeting = f"Hi {name}," if name else "Hi there,"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #eab308 0%, #f59e0b 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 28px; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #eab308; color: #000; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
            .button:hover {{ background: #ca8a04; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌦️ RouteCast</h1>
            </div>
            <div class="content">
                <p>{greeting}</p>
                <p>Welcome to RouteCast! Please verify your email address to get started with weather-smart route planning.</p>
                <p style="text-align: center;">
                    <a href="{verify_url}" class="button">Verify Email Address</a>
                </p>
                <p>Or copy this link into your browser:</p>
                <p style="word-break: break-all; color: #6b7280; font-size: 14px;">{verify_url}</p>
                <p>This link expires in 24 hours.</p>
            </div>
            <div class="footer">
                <p>© 2025 RouteCast Weather. All rights reserved.</p>
                <p>If you didn't create an account, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    result = _send_email(email, "Verify your RouteCast account", html_content)
    logger.info(
        f"[EMAIL] Verification email send result={result} to={email} "
        f"token_head={token[:6] if len(token) >= 6 else token}"
    )
    return result


def send_password_reset_email(email: str, token: str, name: Optional[str] = None) -> bool:
    """Send password reset link"""
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    greeting = f"Hi {name}," if name else "Hi there,"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 28px; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #ef4444; color: #fff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
            .button:hover {{ background: #dc2626; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset</h1>
            </div>
            <div class="content">
                <p>{greeting}</p>
                <p>We received a request to reset your RouteCast password. Click the button below to create a new password:</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </p>
                <p>Or copy this link into your browser:</p>
                <p style="word-break: break-all; color: #6b7280; font-size: 14px;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong> This link expires in 1 hour. If you didn't request a password reset, please ignore this email and your password will remain unchanged.
                </div>
            </div>
            <div class="footer">
                <p>© 2025 RouteCast Weather. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return _send_email(email, "Reset your RouteCast password", html_content)


def send_trial_started_email(email: str, name: Optional[str] = None, plan: str = "monthly") -> bool:
    """Send 'You're All Set' email ONLY after Stripe confirms trial/subscription.

    This must NOT be called on email verification alone — only when
    the user has actually completed checkout and has an active or trialing
    subscription.
    """
    greeting = f"Hi {name}," if name else "Hi there,"
    plan_label = "Annual" if plan == "yearly" else "Monthly"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 28px; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
            .feature {{ display: flex; align-items: flex-start; margin: 15px 0; }}
            .feature-icon {{ font-size: 24px; margin-right: 15px; }}
            .button {{ display: inline-block; background: #22c55e; color: #fff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ You're All Set!</h1>
            </div>
            <div class="content">
                <p>{greeting}</p>
                <p>Your 7-day free trial has started on the <strong>{plan_label}</strong> plan. You have full access to every premium feature — no charges until your trial ends.</p>

                <div class="feature">
                    <span class="feature-icon">🌦️</span>
                    <div>
                        <strong>Route Weather Forecasts</strong>
                        <p style="margin: 5px 0; color: #6b7280;">Get real-time weather conditions along your entire journey.</p>
                    </div>
                </div>

                <div class="feature">
                    <span class="feature-icon">⚠️</span>
                    <div>
                        <strong>Weather Alerts</strong>
                        <p style="margin: 5px 0; color: #6b7280;">Receive push notifications for hazardous conditions.</p>
                    </div>
                </div>

                <div class="feature">
                    <span class="feature-icon">🚛</span>
                    <div>
                        <strong>Trucker &amp; RV Features</strong>
                        <p style="margin: 5px 0; color: #6b7280;">Bridge clearances, truck stops, and more for commercial drivers.</p>
                    </div>
                </div>

                <p style="text-align: center;">
                    <a href="{FRONTEND_URL}" class="button">Open RouteCast</a>
                </p>

                <p style="color: #6b7280; font-size: 14px; text-align: center;">Need to change plans? Go to Settings &gt; Manage Subscription in the app.</p>
            </div>
            <div class="footer">
                <p>&copy; 2025 RouteCast Weather. All rights reserved.</p>
                <p>Questions? Contact us at support@routecast.com</p>
            </div>
        </div>
    </body>
    </html>
    """

    return _send_email(email, "Your RouteCast trial has started! 🚀", html_content)


def send_subscription_confirmation_email(email: str, plan: str, name: Optional[str] = None) -> bool:
    """Send subscription confirmation email"""
    greeting = f"Hi {name}," if name else "Hi there,"
    plan_display = "Monthly" if plan == "monthly" else "Yearly"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 28px; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
            .plan-box {{ background: #fff; border: 2px solid #8b5cf6; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .plan-name {{ font-size: 24px; font-weight: bold; color: #8b5cf6; }}
            .button {{ display: inline-block; background: #8b5cf6; color: #fff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Subscription Confirmed!</h1>
            </div>
            <div class="content">
                <p>{greeting}</p>
                <p>Thank you for subscribing to RouteCast Premium! Your subscription is now active.</p>

                <div class="plan-box">
                    <div class="plan-name">{plan_display} Plan</div>
                    <p style="margin: 10px 0; color: #6b7280;">Full access to all premium features</p>
                </div>

                <p>You now have access to:</p>
                <ul>
                    <li>Unlimited route monitoring</li>
                    <li>Push weather alerts</li>
                    <li>AI-powered recommendations</li>
                    <li>Advanced trucker features</li>
                    <li>Priority support</li>
                </ul>

                <p style="text-align: center;">
                    <a href="{FRONTEND_URL}" class="button">Start Using Premium</a>
                </p>
            </div>
            <div class="footer">
                <p>© 2025 RouteCast Weather. All rights reserved.</p>
                <p>Manage your subscription in the app settings.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return _send_email(email, f"Your RouteCast {plan_display} subscription is active!", html_content)


def send_test_email(to: str, subject: str, text: str) -> bool:
    """Send a simple test email for operational checks."""
    html_content = f"<p>{text}</p>"
    return _send_email(to, subject, html_content)


def send_contact_email(name: str, email: str, message: str, client_ip: str, user_agent: str) -> bool:
    """Send contact form submission to support."""
    subject = f"RouteCast Contact: {name} <{email}>"
    message_html = message.replace("\n", "<br/>")
    html_content = f"""
    <p><strong>Name:</strong> {name}</p>
    <p><strong>Email:</strong> {email}</p>
    <p><strong>Message:</strong><br/>{message_html}</p>
    <hr/>
    <p><strong>IP:</strong> {client_ip}</p>
    <p><strong>User-Agent:</strong> {user_agent}</p>
    """
    return _send_email(CONTACT_TO_EMAIL, subject, html_content)

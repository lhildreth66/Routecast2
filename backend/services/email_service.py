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
BACKEND_URL = (
    os.environ.get('BACKEND_PUBLIC_URL')
    or os.environ.get('BACKEND_URL', '')
    or os.environ.get('EXPO_PUBLIC_BACKEND_URL', '')
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
    verify_base = BACKEND_URL or FRONTEND_URL
    if verify_base.endswith('/api'):
        verify_url = f"{verify_base}/auth/verify-email?token={safe_token}"
    else:
        verify_url = f"{verify_base}/api/auth/verify-email?token={safe_token}"
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


def send_signup_reminder_email(
    email: str,
    name: Optional[str],
    stage: int,
    unsubscribe_url: str,
) -> bool:
    """Send an abandoned-signup reminder email.

    stage: 1 = ~1 hour after signup (gentle nudge)
            2 = ~24 hours after signup (feature highlight)
            3 = ~72 hours after signup (last-chance / urgency)
    """
    greeting = f"Hi {name}," if name else "Hi there,"
    subscription_url = f"{FRONTEND_URL}/subscription"

    if stage == 1:
        subject = "You're almost set up on RouteCast 🌦️"
        headline = "You're Almost Set Up"
        header_gradient = "linear-gradient(135deg, #eab308 0%, #f59e0b 100%)"
        button_color = "#eab308"
        button_text_color = "#000"
        body_intro = (
            "You signed up for RouteCast but haven't started a free trial yet. "
            "It only takes 30 seconds — start planning weather-smart routes today."
        )
        body_extra = ""
        cta_label = "Start My Free Trial"
    elif stage == 2:
        subject = "Don't miss out on smarter route planning 🚗"
        headline = "See What You're Missing"
        header_gradient = "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)"
        button_color = "#3b82f6"
        button_text_color = "#fff"
        body_intro = (
            "Thousands of drivers use RouteCast to dodge hazards, check bridge clearances, "
            "and get AI-powered weather summaries for every mile of their trip."
        )
        body_extra = """
                <ul style="margin: 12px 0; padding-left: 20px; color: #374151;">
                    <li>⚠️ Real-time hazard alerts along your route</li>
                    <li>🌉 Bridge height clearances for RVs &amp; trucks</li>
                    <li>🤖 AI weather summaries for the whole journey</li>
                    <li>🛎️ Push notifications before you leave</li>
                </ul>"""
        cta_label = "Start Free Trial — No Credit Card Needed"
    else:
        subject = "Last chance: your free RouteCast trial is waiting ⏰"
        headline = "Your Free Trial Is Waiting"
        header_gradient = "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
        button_color = "#ef4444"
        button_text_color = "#fff"
        body_intro = (
            "This is a friendly reminder that your free 7-day trial is just one tap away. "
            "After the trial you can cancel anytime — no strings attached."
        )
        body_extra = ""
        cta_label = "Claim My Free Trial Now"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {header_gradient}; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ color: #fff; margin: 0; font-size: 26px; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: {button_color}; color: {button_text_color}; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; font-size: 16px; }}
        .footer {{ text-align: center; padding: 20px; color: #9ca3af; font-size: 12px; }}
        .unsubscribe {{ color: #9ca3af; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌦️ {headline}</h1>
        </div>
        <div class="content">
            <p>{greeting}</p>
            <p>{body_intro}</p>{body_extra}
            <p style="text-align: center;">
                <a href="{subscription_url}" class="button">{cta_label}</a>
            </p>
            <p style="color: #6b7280; font-size: 14px;">
                Already subscribed or not interested? You can
                <a href="{unsubscribe_url}" style="color: #6b7280;">unsubscribe from these reminders</a>.
            </p>
        </div>
        <div class="footer">
            <p>&copy; 2025 RouteCast Weather. All rights reserved.</p>
            <p><a href="{unsubscribe_url}" class="unsubscribe">Unsubscribe from reminder emails</a></p>
        </div>
    </div>
</body>
</html>"""

    logger.info(
        "[reminder_email] sending stage=%d to=%s",
        stage, email,
    )
    return _send_email(email, subject, html_content)


def send_signup_notification_email(
    user_id: str,
    email: str,
    name: Optional[str],
    created_at: str,
    email_verified: bool = False,
) -> bool:
    """Send an internal notification to support when a new user signs up."""
    subject = "New RouteCast Signup"
    name_display = name or "(not provided)"
    verified_label = "Yes" if email_verified else "No"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; }}
        .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        td {{ padding: 8px 12px; border: 1px solid #e5e7eb; }}
        td:first-child {{ font-weight: bold; background: #f9fafb; width: 40%; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>&#128228; New RouteCast Signup</h2>
        <table>
            <tr><td>Name</td><td>{name_display}</td></tr>
            <tr><td>Email</td><td>{email}</td></tr>
            <tr><td>User ID</td><td>{user_id}</td></tr>
            <tr><td>Created At</td><td>{created_at}</td></tr>
            <tr><td>Email Verified</td><td>{verified_label}</td></tr>
        </table>
    </div>
</body>
</html>"""

    return _send_email(CONTACT_TO_EMAIL, subject, html_content)


def send_verification_reminder_email(
    email: str,
    name: Optional[str],
    stage: int,
    verify_url: str,
    unsubscribe_url: str,
) -> bool:
    """Send a verification nudge email with a fresh verify link.

    stage 1: ~1 h after signup  — gentle nudge, link is valid (within 24 h)
    stage 2: ~24 h after signup — stronger nudge, fresh token issued by caller

    Called only by run_verification_reminders.py. Never touches billing or
    subscription logic.
    """
    greeting = f"Hi {name}," if name else "Hi there,"

    if stage == 1:
        subject  = "Please verify your RouteCast email \U0001f326️"
        headline = "One Step Left"
        gradient = "linear-gradient(135deg, #eab308 0%, #f59e0b 100%)"
        btn_bg   = "#eab308"
        btn_fg   = "#000"
        body     = (
            "You're almost in! Click the button below to verify your "
            "email address and unlock RouteCast's weather-smart route planning."
        )
    else:
        subject  = "Still waiting to verify your RouteCast email \u23f3"
        headline = "Don't Forget to Verify"
        gradient = "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)"
        btn_bg   = "#3b82f6"
        btn_fg   = "#fff"
        body     = (
            "Your RouteCast account is ready \u2014 we just need you to verify "
            "your email before you can start planning safer drives."
        )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {gradient}; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ color: #fff; margin: 0; font-size: 26px; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: {btn_bg}; color: {btn_fg}; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; font-size: 16px; }}
        .footer {{ text-align: center; padding: 20px; color: #9ca3af; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>\U0001f326\ufe0f {headline}</h1></div>
        <div class="content">
            <p>{greeting}</p>
            <p>{body}</p>
            <p style="text-align: center;">
                <a href="{verify_url}" class="button">Verify My Email</a>
            </p>
            <p style="color: #6b7280; font-size: 14px;">Or copy this link into your browser:<br/>
                <span style="word-break: break-all;">{verify_url}</span></p>
            <p style="color: #6b7280; font-size: 14px;">This link expires in 24 hours.</p>
            <p style="color: #6b7280; font-size: 14px;">
                <a href="{unsubscribe_url}" style="color: #9ca3af;">Unsubscribe from these reminders</a>
            </p>
        </div>
        <div class="footer">
            <p>&copy; 2025 RouteCast Weather. All rights reserved.</p>
            <p><a href="{unsubscribe_url}" style="color: #9ca3af;">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>"""

    logger.info("[verify_reminder_email] sending stage=%d to=%s", stage, email)
    return _send_email(email, subject, html_content)


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

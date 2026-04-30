import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key

FROM_ADDRESS = "BuildTest AI <noreply@buildtest.asia>"


def _verification_code_html(code: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1a1a1a; margin-bottom: 16px;">BuildTest AI 验证码</h2>
        <p style="color: #4a4a4a; font-size: 15px; line-height: 1.6;">
            您的验证码是：
        </p>
        <div style="background: #f4f4f5; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #1a1a1a;">{code}</span>
        </div>
        <p style="color: #71717a; font-size: 13px; line-height: 1.5;">
            验证码 5 分钟内有效。如果这不是您的操作，请忽略此邮件。
        </p>
    </div>
    """


async def send_verification_email(email: str, code: str) -> bool:
    """发送验证码邮件。成功返回 True，失败返回 False。"""
    try:
        resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": [email],
                "subject": "BuildTest AI - 邮箱验证码",
                "html": _verification_code_html(code),
            }
        )
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", email)
        return False

from unittest.mock import Mock, patch

import pytest

from app.services.email_service import send_verification_email


@pytest.mark.asyncio
@patch("app.services.email_service.resend.Emails.send")
async def test_send_verification_email_calls_resend(mock_send):
    mock_send.return_value = {"id": "msg_123"}
    result = await send_verification_email("test@example.com", "123456")
    assert result is True
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0][0]
    assert call_args["to"] == ["test@example.com"]
    assert "123456" in call_args["html"]


@pytest.mark.asyncio
@patch("app.services.email_service.resend.Emails.send")
async def test_send_verification_email_returns_false_on_error(mock_send):
    mock_send.side_effect = Exception("resend error")
    result = await send_verification_email("test@example.com", "123456")
    assert result is False

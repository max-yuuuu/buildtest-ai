from __future__ import annotations


class ChatDomainError(Exception):
    code: str = "CHAT_DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ModeNotImplementedError(ChatDomainError):
    code = "MODE_NOT_IMPLEMENTED"

    def __init__(self, mode: str) -> None:
        super().__init__(f"chat mode `{mode}` is not implemented in MVP")
        self.mode = mode

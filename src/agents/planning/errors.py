"""Planning-specific errors that must not leak as raw HTTP 500s."""

from __future__ import annotations


class PlanningFailedError(Exception):
    """Raised when Planning cannot complete a PLAN task for a recoverable/external reason.

    The API maps this to a user-facing 200 response so FastAPI does not return HTTP 500.
    Supervisor / Gateway / Review are unchanged.
    """

    def __init__(
        self,
        user_message: str,
        *,
        session_id: str = "",
        correlation_id: str = "",
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.session_id = session_id
        self.correlation_id = correlation_id

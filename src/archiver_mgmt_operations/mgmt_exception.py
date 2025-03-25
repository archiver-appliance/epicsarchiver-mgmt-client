class BaseMgmtError(Exception):
    """Base exception for mgmt operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

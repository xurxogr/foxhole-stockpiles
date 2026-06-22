"""PAK validation result model."""


class PakValidationResult:
    """Result of PAK file validation for required assets."""

    def __init__(self) -> None:
        """Initialize validation result."""
        self.is_valid: bool = False
        self.has_crate_icon: bool = False
        self.has_subicons: bool = False
        self.subicons_count: int = 0
        self.error_message: str = ""
        self.files_found: set[str] = set()

    def __str__(self) -> str:
        """Return string representation."""
        if self.is_valid:
            return f"Valid: crate_icon={self.has_crate_icon}, subicons={self.subicons_count}"
        return f"Invalid: {self.error_message}"

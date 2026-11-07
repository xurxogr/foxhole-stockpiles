"""One structure in the display names extracted from the game."""

from pydantic import BaseModel, ConfigDict, Field


class DisplayNameEntry(BaseModel):
    """The names of a structure, as fs-assets extracts them from the game."""

    code: str = Field(alias="CodeName", min_length=1)
    name: str = Field(alias="DisplayName", min_length=1)
    names: dict[str, str] = Field(alias="DisplayNameLocales", default_factory=dict)
    is_stockpile: bool = Field(alias="Stockpile", default=False)

    model_config = ConfigDict(frozen=True, extra="ignore")

    def name_in(self, language: str) -> str:
        """Get the name in a language, in English if the game has none.

        Args:
            language (str): The language code.

        Returns:
            str: The name.
        """
        return self.names.get(language) or self.name

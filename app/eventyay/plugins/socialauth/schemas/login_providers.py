from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    state: bool = Field(default=False, description="State of this provider")
    client_id: str = Field(default="", description="Client ID of this provider")
    secret: str = Field(default="", description="Secret of this provider")
    is_preferred: bool = Field(default=False, description="Preferred login method")


class LoginProviders(BaseModel):
    mediawiki: ProviderConfig = Field(default_factory=ProviderConfig)
    github: ProviderConfig = Field(default_factory=ProviderConfig)
    google: ProviderConfig = Field(default_factory=ProviderConfig)

    class Config:
        extra = "forbid"

    def _providers(self) -> dict[str, ProviderConfig]:
        """
        Internal helper: Return all provider fields as a name -> ProviderConfig mapping.
        Used to iterate over all providers regardless of their enabled state.
        """
        return {name: getattr(self, name) for name in self.model_fields}

    def get_enabled_providers(self) -> dict[str, ProviderConfig]:
        """
        Get all enabled providers (where state=True).
        
        Returns:
            dict[str, ProviderConfig]: Only enabled providers
        """
        return {
            name: provider
            for name, provider in self._providers().items()
            if provider.state  # Filter only enabled providers
        }

    def get_preferred_provider(self) -> tuple[str, ProviderConfig] | None:
        """
        Get the preferred provider if one exists and is enabled.
        
        Returns:
            tuple[str, ProviderConfig] | None: (provider_name, ProviderConfig) or None
        """
        for name, provider in self._providers().items():
            # Return first provider that is both enabled and marked as preferred
            if provider.state and provider.is_preferred:
                return name, provider
        return None  # No preferred provider found

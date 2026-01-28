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
        Iterate over all providers regardless of their enabled state.
        """
        return {name: getattr(self, name) for name in self.model_fields}

    
    def get_enabled_providers(self) -> "LoginProviders":
        """
        Get all enabled providers.
        """
        # Build a dict of only enabled providers.
        enabled_data = {
            name: getattr(self, name)  # fetch the ProviderConfig
            for name in self.model_fields
            if getattr(self, name).state
        }

        # Return a new LoginProviders object
        return LoginProviders(**enabled_data)

        
    def get_preferred_provider(self) -> tuple[str, ProviderConfig] | None:
        """
        Get the preferred provider if one exists and is enabled.
        """
        for name, provider in self._providers().items():
            # Return first provider that is both enabled and marked as preferred
            if provider.state and provider.is_preferred:
                return name, provider
        return None  # No preferred provider found

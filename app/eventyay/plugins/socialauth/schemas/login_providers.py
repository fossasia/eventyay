from pydantic import BaseModel, Field, model_validator


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

    def providers(self) -> dict[str, ProviderConfig]:
        """
        Return all provider fields as a name -> ProviderConfig mapping.
        Iterate over all providers regardless of their enabled state.
        """
        return {name: getattr(self, name) for name in self.model_fields}

    @model_validator(mode="after")
    def ensure_single_preferred(self) -> "LoginProviders":
        """
        Ensure that at most one enabled provider has is_preferred=True.
        Automatically clear preferred status if the provider is disabled.
        
        Rules enforced:
        1. If a provider is disabled (state=False), it cannot be preferred (is_preferred=False)
        2. At most one enabled provider can be marked as preferred
        3. If multiple enabled providers are marked preferred, keep only the first one
        """
        preferred_found = False
        updates = {}

        for name, provider in self.providers().items():
            # Rule 1: Clear is_preferred for any disabled provider
            if not provider.state and provider.is_preferred:
                updates[name] = ProviderConfig(
                    state=provider.state,
                    client_id=provider.client_id,
                    secret=provider.secret,
                    is_preferred=False  # Disabled providers cannot be preferred
                )
            # Rule 2 & 3: Ensure only one enabled provider is preferred
            elif provider.state and provider.is_preferred:
                if not preferred_found:
                    preferred_found = True  # keep the first enabled preferred provider
                else:
                    # Clear extra preferred flags from duplicate preferred providers
                    updates[name] = ProviderConfig(
                        state=provider.state,
                        client_id=provider.client_id,
                        secret=provider.secret,
                        is_preferred=False  # Clear the duplicate preference
                    )

        # Apply updates if any
        if updates:
            for name, updated_provider in updates.items():
                setattr(self, name, updated_provider)

        return self

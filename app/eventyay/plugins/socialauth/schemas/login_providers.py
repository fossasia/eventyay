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
           (based on alphabetical order of provider names for deterministic behavior)
        """
        preferred_found = False
        updates = {}

        # Sort by provider name to ensure deterministic behavior when multiple
        # providers are marked as preferred
        for name in sorted(self.model_fields.keys()):
            provider = getattr(self, name)
            
            # Rule 1: Clear is_preferred for any disabled provider
            if not provider.state and provider.is_preferred:
                # Use model_copy to preserve all fields and only update is_preferred
                updates[name] = provider.model_copy(update={"is_preferred": False})
            # Rule 2 & 3: Ensure only one enabled provider is preferred
            elif provider.state and provider.is_preferred:
                if not preferred_found:
                    preferred_found = True  # keep the first enabled preferred provider
                else:
                    # Clear extra preferred flags from duplicate preferred providers
                    # Use model_copy to preserve all fields and only update is_preferred
                    updates[name] = provider.model_copy(update={"is_preferred": False})

        # Apply updates if any
        if updates:
            for name, updated_provider in updates.items():
                setattr(self, name, updated_provider)

        return self

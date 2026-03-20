from pydantic import BaseModel, ConfigDict, Field


class ProviderConfig(BaseModel):
    state: bool = Field(description='State of this provider', default=False)
    client_id: str = Field(description='Client ID of this provider', default='')
    secret: str = Field(description='Secret of this provider', default='')


class LoginProviders(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mediawiki: ProviderConfig = Field(default_factory=ProviderConfig)
    github: ProviderConfig = Field(default_factory=ProviderConfig)
    google: ProviderConfig = Field(default_factory=ProviderConfig)
    preferred_provider: str = Field(description='Preferred login provider', default='')


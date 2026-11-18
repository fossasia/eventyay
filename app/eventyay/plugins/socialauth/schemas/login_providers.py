from pydantic import BaseModel, ConfigDict, Field


class ProviderConfig(BaseModel):
    state: bool = Field(description='State of this providers', default=False)
    client_id: str = Field(description='Client ID of this provider', default='')
    secret: str = Field(description='Secret of this provider', default='')
    is_preferred: bool = Field(description='Whether this provider is the preferred login method', default=False)
    server_url: str = Field(description='OIDC server / issuer URL (required for openid_connect)', default='')
    name: str = Field(description='Display name of this provider (optional for openid_connect)', default='')


class LoginProviders(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mediawiki: ProviderConfig = Field(default_factory=ProviderConfig)
    github: ProviderConfig = Field(default_factory=ProviderConfig)
    google: ProviderConfig = Field(default_factory=ProviderConfig)
    openid_connect: ProviderConfig = Field(default_factory=ProviderConfig)

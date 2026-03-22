from typing import Optional, Union

from pydantic import BaseModel, model_validator


class CardDetails(BaseModel):
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None


class IdealDetails(BaseModel):
    bank: Optional[str] = None


class BancontactDetails(BaseModel):
    bankname: Optional[str] = None


class SofortDetails(BaseModel):
    country: Optional[str] = None
    iban_last4: Optional[str] = None
    bank_name: Optional[str] = None


class EPSDetails(BaseModel):
    bank: Optional[str] = None


class P24Details(BaseModel):
    bank: Optional[str] = None


class PaymentMethodDetails(BaseModel):
    card: Optional[CardDetails] = None
    ideal: Optional[IdealDetails] = None
    bancontact: Optional[BancontactDetails] = None
    sofort: Optional[SofortDetails] = None
    eps: Optional[EPSDetails] = None
    p24: Optional[P24Details] = None


class LatestCharge(BaseModel):
    payment_method_details: Optional[PaymentMethodDetails] = None


class Source(BaseModel):
    card: Optional[CardDetails] = None
    ideal: Optional[IdealDetails] = None
    bancontact: Optional[BancontactDetails] = None
    sofort: Optional[SofortDetails] = None
    eps: Optional[EPSDetails] = None
    p24: Optional[P24Details] = None


class PaymentInfoData(BaseModel):
    latest_charge: Optional[Union[str, LatestCharge]] = None
    source: Optional[Source] = None

    @model_validator(mode="before")
    def check_latest_charge_or_source(cls, values):
        latest_charge = values.get("latest_charge")
        source = values.get("source")
        if not latest_charge and not source:
            raise ValueError("Either 'latest_charge' or 'source' must be provided.")
        return values

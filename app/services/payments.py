"""Payment providers.

A provider does three things: open a checkout, verify a webhook signature and
normalise the event. ``MockProvider`` implements all three locally so the whole
flow — checkout, callback, receipt, notification — can be run and tested with
no third-party account.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.exceptions import ServiceUnavailable, ValidationFailed


def new_reference(prefix: str = "pay") -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


@dataclass(slots=True)
class CheckoutResult:
    reference: str
    checkout_url: str
    provider: str
    provider_reference: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalisedEvent:
    """Provider-agnostic shape the webhook handler works with."""

    event_id: str
    event_type: str          # ``payment.succeeded`` | ``payment.failed`` | ``payment.refunded``
    reference: str | None
    provider_reference: str | None
    amount_minor: int
    currency: str
    fee_minor: int = 0
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_checkout(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        description: str,
        payer_email: str | None,
        success_url: str,
        cancel_url: str,
        meta: dict[str, Any],
    ) -> CheckoutResult: ...

    @abstractmethod
    def verify_signature(self, payload: bytes, signature: str | None) -> bool: ...

    @abstractmethod
    def parse_event(self, payload: dict[str, Any]) -> NormalisedEvent: ...


class MockProvider(PaymentProvider):
    """Local provider. The checkout URL points back at our own confirm route."""

    name = "mock"

    def create_checkout(self, **kwargs: Any) -> CheckoutResult:
        reference = kwargs["reference"]
        return CheckoutResult(
            reference=reference,
            checkout_url=(
                f"{settings.SITE_URL}/checkout/{reference}"
                f"?amount={kwargs['amount_minor']}&currency={kwargs['currency']}"
            ),
            provider=self.name,
            provider_reference=f"mock_{reference}",
            raw={"simulated": True},
        )

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        expected = hmac.new(
            settings.SECRET_KEY.encode(), payload, hashlib.sha256
        ).hexdigest()
        return bool(signature) and hmac.compare_digest(expected, signature or "")

    def sign(self, payload: bytes) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()

    def parse_event(self, payload: dict[str, Any]) -> NormalisedEvent:
        return NormalisedEvent(
            event_id=payload.get("id") or secrets.token_hex(8),
            event_type=payload.get("type", "payment.succeeded"),
            reference=payload.get("reference"),
            provider_reference=payload.get("provider_reference"),
            amount_minor=int(payload.get("amount_minor", 0)),
            currency=payload.get("currency", settings.DEFAULT_CURRENCY),
            failure_reason=payload.get("failure_reason"),
            raw=payload,
        )


class StripeProvider(PaymentProvider):
    name = "stripe"

    def create_checkout(self, **kwargs: Any) -> CheckoutResult:
        if not settings.STRIPE_SECRET_KEY:
            raise ServiceUnavailable("Stripe is selected but no secret key is set.")
        try:
            import stripe  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ServiceUnavailable("Install the 'stripe' package to take card payments.") from exc

        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="payment",
            client_reference_id=kwargs["reference"],
            customer_email=kwargs.get("payer_email"),
            success_url=kwargs["success_url"],
            cancel_url=kwargs["cancel_url"],
            metadata={"reference": kwargs["reference"], **kwargs.get("meta", {})},
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": kwargs["currency"].lower(),
                        "unit_amount": kwargs["amount_minor"],
                        "product_data": {"name": kwargs["description"][:120]},
                    },
                }
            ],
        )
        return CheckoutResult(
            reference=kwargs["reference"],
            checkout_url=session.url,
            provider=self.name,
            provider_reference=session.id,
            raw={"session_id": session.id},
        )

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        if not settings.STRIPE_WEBHOOK_SECRET:
            return False
        try:
            import stripe  # noqa: PLC0415

            stripe.Webhook.construct_event(
                payload, signature or "", settings.STRIPE_WEBHOOK_SECRET
            )
            return True
        except Exception:
            return False

    def parse_event(self, payload: dict[str, Any]) -> NormalisedEvent:
        obj = payload.get("data", {}).get("object", {})
        mapping = {
            "checkout.session.completed": "payment.succeeded",
            "payment_intent.payment_failed": "payment.failed",
            "charge.refunded": "payment.refunded",
        }
        return NormalisedEvent(
            event_id=payload.get("id", ""),
            event_type=mapping.get(payload.get("type", ""), payload.get("type", "")),
            reference=obj.get("client_reference_id") or obj.get("metadata", {}).get("reference"),
            provider_reference=obj.get("id"),
            amount_minor=int(obj.get("amount_total") or obj.get("amount") or 0),
            currency=(obj.get("currency") or settings.DEFAULT_CURRENCY).upper(),
            failure_reason=(obj.get("last_payment_error") or {}).get("message"),
            raw=payload,
        )


class PaystackProvider(PaymentProvider):
    name = "paystack"

    def create_checkout(self, **kwargs: Any) -> CheckoutResult:
        if not settings.PAYSTACK_SECRET_KEY:
            raise ServiceUnavailable("Paystack is selected but no secret key is set.")
        import httpx  # noqa: PLC0415

        response = httpx.post(
            "https://api.paystack.co/transaction/initialize",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            json={
                "email": kwargs.get("payer_email") or settings.OWNER_EMAIL,
                "amount": kwargs["amount_minor"],
                "currency": kwargs["currency"],
                "reference": kwargs["reference"],
                "callback_url": kwargs["success_url"],
                "metadata": kwargs.get("meta", {}),
            },
            timeout=20,
        )
        body = response.json()
        if not body.get("status"):
            raise ValidationFailed(body.get("message", "Paystack rejected the checkout."))
        data = body["data"]
        return CheckoutResult(
            reference=kwargs["reference"],
            checkout_url=data["authorization_url"],
            provider=self.name,
            provider_reference=data["reference"],
            raw=data,
        )

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        secret = settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
        if not secret:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
        return bool(signature) and hmac.compare_digest(expected, signature)

    def parse_event(self, payload: dict[str, Any]) -> NormalisedEvent:
        data = payload.get("data", {})
        mapping = {
            "charge.success": "payment.succeeded",
            "charge.failed": "payment.failed",
            "refund.processed": "payment.refunded",
        }
        return NormalisedEvent(
            event_id=str(data.get("id") or ""),
            event_type=mapping.get(payload.get("event", ""), payload.get("event", "")),
            reference=data.get("reference"),
            provider_reference=str(data.get("id") or ""),
            amount_minor=int(data.get("amount") or 0),
            currency=(data.get("currency") or settings.DEFAULT_CURRENCY).upper(),
            fee_minor=int(data.get("fees") or 0),
            failure_reason=data.get("gateway_response"),
            raw=payload,
        )


class FlutterwaveProvider(PaymentProvider):
    """Flutterwave Standard checkout — widely used across West Africa,
    with support for cards, bank transfer, USSD and mobile money."""

    name = "flutterwave"

    def create_checkout(self, **kwargs: Any) -> CheckoutResult:
        if not settings.FLUTTERWAVE_SECRET_KEY:
            raise ServiceUnavailable("Flutterwave is selected but no secret key is set.")
        import httpx  # noqa: PLC0415

        response = httpx.post(
            "https://api.flutterwave.com/v3/payments",
            headers={"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"},
            json={
                "tx_ref": kwargs["reference"],
                "amount": kwargs["amount_minor"] / 100,
                "currency": kwargs["currency"],
                "redirect_url": kwargs["success_url"],
                "customer": {
                    "email": kwargs.get("payer_email") or settings.OWNER_EMAIL,
                    "name": kwargs.get("payer_name") or "Guest",
                },
                "customizations": {"title": kwargs["description"][:60]},
                "meta": kwargs.get("meta", {}),
            },
            timeout=20,
        )
        body = response.json()
        if body.get("status") != "success":
            raise ValidationFailed(body.get("message", "Flutterwave rejected the checkout."))
        return CheckoutResult(
            reference=kwargs["reference"],
            checkout_url=body["data"]["link"],
            provider=self.name,
            provider_reference=kwargs["reference"],
            raw=body["data"],
        )

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        secret = settings.FLUTTERWAVE_WEBHOOK_SECRET
        if not secret:
            return False
        # Flutterwave sends the shared secret back verbatim as verif-hash,
        # rather than an HMAC of the body.
        return bool(signature) and hmac.compare_digest(secret, signature or "")

    def parse_event(self, payload: dict[str, Any]) -> NormalisedEvent:
        data = payload.get("data", {})
        mapping = {
            "successful": "payment.succeeded",
            "failed": "payment.failed",
        }
        status = data.get("status", "")
        return NormalisedEvent(
            event_id=str(data.get("id") or ""),
            event_type=mapping.get(status, f"payment.{status}" if status else "payment.unknown"),
            reference=data.get("tx_ref"),
            provider_reference=str(data.get("id") or ""),
            amount_minor=round(float(data.get("amount") or 0) * 100),
            currency=(data.get("currency") or settings.DEFAULT_CURRENCY).upper(),
            fee_minor=round(float(data.get("app_fee") or 0) * 100),
            failure_reason=data.get("processor_response"),
            raw=payload,
        )


_PROVIDERS: dict[str, type[PaymentProvider]] = {
    "mock": MockProvider,
    "stripe": StripeProvider,
    "paystack": PaystackProvider,
    "flutterwave": FlutterwaveProvider,
}


def get_provider(name: str | None = None) -> PaymentProvider:
    key = (name or settings.PAYMENT_PROVIDER).lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise ValidationFailed(f"Unknown payment provider: {key}.")
    return provider()


def format_amount(amount_minor: int, currency: str = "USD") -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "NGN": "₦"}
    return f"{symbols.get(currency, '')}{amount_minor / 100:,.2f}"

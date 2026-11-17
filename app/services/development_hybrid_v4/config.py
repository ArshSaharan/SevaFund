"""Settings for hybrid v4 (development only).  Nothing in production imports this package."""
import hashlib
import json

POLICY_VERSION = "hybrid-v4-dev-1"

SETTINGS = {
    # The goal may exceed the cost issuer's independently stated need (after other payers) by at most 5 %.
    "amount_confirmation_tolerance": 0.05,
    # A campaign whose only open item is formal cost evidence may be routed to assisted cost confirmation.
    "assisted_cost_route": True,
    # Bank account numbers shorter than this are ignored by the payment-account check.
    "payment_account_min_digits": 9,
}

# Every one of these must be confirmed through an independently sourced contact before activation.
REQUIRED_CHECKS = ("BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION", "AMOUNT")


def digest() -> str:
    return hashlib.sha256(json.dumps({"policy": POLICY_VERSION, "settings": SETTINGS, "checks": REQUIRED_CHECKS},
                                     sort_keys=True).encode()).hexdigest()[:16]

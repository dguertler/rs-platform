import os
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


def create_checkout_session(email: str) -> str:
    price_id = os.environ.get('STRIPE_PRICE_ID', '')
    app_url  = os.environ.get('APP_URL', 'http://localhost:8000')
    session  = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        success_url=app_url + '/?upgraded=1',
        cancel_url=app_url + '/',
    )
    return session.url


def parse_webhook(payload: bytes, sig: str):
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    return stripe.Webhook.construct_event(payload, sig, secret)

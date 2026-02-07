# app/auth/utils.py
import secrets
from datetime import datetime, timedelta

def generate_reset_token():
    return secrets.token_urlsafe(32)

def reset_token_expired(user):
    return not user.reset_token_expires or user.reset_token_expires < datetime.utcnow()

from flask import current_app, render_template
from app import mail
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
import os

def get_token_serializer():
    """Creates a secure token serializer using the app's secret key"""
    secret_key = current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(secret_key)

def send_email(subject, recipients, html_body, text_body=""):
    """General email sending function"""
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)

def send_password_reset_email(user):
    """Generate password reset email with a secure token"""
    token = generate_reset_token(user.email)
    send_email(
        'Reset Your Password',
        recipients=[user.email],
        html_body=render_template('email/reset_password.html', user=user, token=token),
        text_body=render_template('email/reset_password.txt', user=user, token=token)
    )

def send_verification_email(user):
    """Send verification email to new users"""
    token = generate_verification_token(user.email)
    send_email(
        'Verify Your Email Address',
        recipients=[user.email],
        html_body=render_template('email/verification.html', user=user, token=token),
        text_body=render_template('email/verification.txt', user=user, token=token)
    )

def generate_reset_token(email):
    """Generate a timed token for password reset"""
    s = get_token_serializer()
    return s.dumps(email, salt='password-reset')

def generate_verification_token(email):
    """Generate a timed token for email verification"""
    s = get_token_serializer()
    return s.dumps(email, salt='email-verification')

def verify_reset_token(token, max_age=3600):
    """Verify the password reset token"""
    s = get_token_serializer()
    try:
        email = s.loads(token, salt='password-reset', max_age=max_age)
        return email
    except:
        return None

def verify_verification_token(token, max_age=86400):
    """Verify the email verification token"""
    s = get_token_serializer()
    try:
        email = s.loads(token, salt='email-verification', max_age=max_age)
        return email
    except:
        return None
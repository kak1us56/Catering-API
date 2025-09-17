from celery import shared_task
from django.core.mail import send_mail

@shared_task(queue="low_priority")
def send_user_activation_email_task(email: str, activation_key: str):
    activation_link = f"https://frontend.catering.com/activation/{activation_key}"
    send_mail(
        subject="User Activation",
        message=f"Please, activate your account: {activation_link}",
        from_email="admin@catering.com",
        recipient_list=[email],
    )
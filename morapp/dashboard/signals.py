from django.db.models.signals import post_save
from django.dispatch import receiver
from website.models import Order, Transaction, PurchasedReport, UserProfile
from dashboard.utils import send_order_confirmation_email, send_payment_success_email, send_new_client_notification

@receiver(post_save, sender=Order)
def order_created_handler(sender, instance, created, **kwargs):
    if created:
        send_order_confirmation_email(instance)

@receiver(post_save, sender=Transaction)
def transaction_confirmed_handler(sender, instance, created, **kwargs):
    if instance.confirmed and created:
        send_payment_success_email(instance)

@receiver(post_save, sender=UserProfile)
def user_profile_created_handler(sender, instance, created, **kwargs):
    if created and instance.is_client():
        send_new_client_notification(instance)
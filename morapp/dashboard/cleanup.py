from django.utils import timezone
from datetime import timedelta
import os
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Order, Transaction, PurchasedReport, UserProfile
from django.db.models import Sum, Count

logger = logging.getLogger('dashboard')

def cleanup_expired_orders():
    try:
        expiry_time = timezone.now() - timedelta(minutes=30)
        expired_orders = Order.objects.filter(status='pending', created_at__lt=expiry_time)
        count = expired_orders.count()
        expired_orders.update(status='cancelled')
        logger.info(f"Cleaned up {count} expired orders")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up expired orders: {e}")
        return 0

def cleanup_temp_files():
    try:
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        if not os.path.exists(temp_dir):
            return 0
        
        count = 0
        cutoff_time = timezone.now().timestamp() - (24 * 60 * 60)
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    count += 1
                except OSError:
                    pass
        logger.info(f"Cleaned up {count} temporary files")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")
        return 0

def generate_monthly_report():
    try:
        today = timezone.now().date()
        first_day_current_month = today.replace(day=1)
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        first_day_previous_month = last_day_previous_month.replace(day=1)
        
        monthly_data = {
            'period': first_day_previous_month.strftime('%B %Y'),
            'revenue': Transaction.objects.filter(
                confirmed=True,
                paid_at__date__range=[first_day_previous_month, last_day_previous_month]
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'orders': Order.objects.filter(
                status='paid',
                created_at__date__range=[first_day_previous_month, last_day_previous_month]
            ).count(),
            'new_clients': UserProfile.objects.filter(
                profile_type='Client',
                join_date__date__range=[first_day_previous_month, last_day_previous_month]
            ).count(),
            'reports_sold': PurchasedReport.objects.filter(
                purchased_on__date__range=[first_day_previous_month, last_day_previous_month]
            ).count(),
        }
        
        subject = f"Monthly Business Report - {monthly_data['period']}"
        html_message = render_to_string('emails/monthly_report.html', {
            'data': monthly_data,
            'site_url': settings.FRONTEND_URL
        })
        plain_message = strip_tags(html_message)
        management_emails = UserProfile.objects.filter(profile_type='Management').values_list('user__email', flat=True)
        
        if management_emails:
            send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, list(management_emails), html_message=html_message)
        logger.info(f"Monthly report generated and sent for {monthly_data['period']}")
        return True
    except Exception as e:
        logger.error(f"Error generating monthly report: {e}")
        return False
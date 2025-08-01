from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.db.models import Sum, Count
from website.models import UserProfile, Report, Order, Transaction, PurchasedReport
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO
import PyPDF2
import logging

logger = logging.getLogger('dashboard')

def generate_order_number():
    import uuid
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"

def generate_transaction_id():
    import uuid
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"

def send_order_confirmation_email(order):
    try:
        subject = f'Order Confirmation - {order.order_number}'
        html_message = render_to_string('emails/order_confirmation.html', {'order': order})
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [order.client.email],
            html_message=html_message
        )
        return True
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {str(e)}")
        return False

def send_payment_success_email(transaction):
    try:
        subject = f'Payment Successful - Order {transaction.order.order_number}'
        html_message = render_to_string('emails/payment_success.html', {'transaction': transaction})
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [transaction.order.client.email],
            html_message=html_message
        )
        return True
    except Exception as e:
        logger.error(f"Error sending payment success email: {str(e)}")
        return False

def send_new_client_notification(user_profile):
    try:
        subject = f'New Client Registration - {user_profile.user.username}'
        html_message = render_to_string('emails/new_client.html', {
            'user': user_profile.user,
            'profile': user_profile
        })
        plain_message = strip_tags(html_message)
        management_emails = UserProfile.objects.filter(profile_type='Management').values_list('user__email', flat=True)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            management_emails,
            html_message=html_message
        )
        return True
    except Exception as e:
        logger.error(f"Error sending new client notification: {str(e)}")
        return False

def calculate_dashboard_stats(user_type, user=None):
    stats = {}
    if user_type == 'client' and user:
        stats['total_reports_purchased'] = PurchasedReport.objects.filter(client=user).count()
        stats['total_amount_spent'] = Transaction.objects.filter(order__client=user, confirmed=True).aggregate(total=Sum('amount'))['total'] or 0.0
        stats['pending_orders'] = Order.objects.filter(client=user, status='pending').count()
    elif user_type == 'admin':
        stats['total_revenue'] = Transaction.objects.filter(confirmed=True).aggregate(total=Sum('amount'))['total'] or 0.0
        stats['total_clients'] = UserProfile.objects.filter(profile_type='Client').count()
        stats['total_reports'] = Report.objects.count()
        stats['total_orders'] = Order.objects.count()
    return stats

def get_monthly_revenue_data(months=12):
    from django.utils import timezone
    from datetime import datetime, timedelta
    today = timezone.now().date()
    data = []
    for i in range(months):
        month_start = today.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        revenue = Transaction.objects.filter(
            confirmed=True,
            paid_at__date__range=[month_start, month_end]
        ).aggregate(total=Sum('amount'))['total'] or 0.0
        order_count = Transaction.objects.filter(
            confirmed=True,
            paid_at__date__range=[month_start, month_end]
        ).count()
        reports_sold = PurchasedReport.objects.filter(
            purchased_on__date__range=[month_start, month_end]
        ).count()
        data.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': float(revenue),
            'order_count': order_count,
            'reports_sold': reports_sold
        })
    return list(reversed(data))

def get_top_selling_reports(limit=10):
    reports = Report.objects.annotate(
        purchase_count=Count('purchasedreport'),
        total_revenue=Sum('orderitem__price')
    ).order_by('-purchase_count')[:limit]
    return [
        {
            'title': report.title,
            'purchase_count': report.purchase_count,
            'total_revenue': float(report.total_revenue or 0)
        }
        for report in reports
    ]

def validate_file_upload(file, allowed_extensions=None, max_size_mb=10):
    if not allowed_extensions:
        allowed_extensions = ['.pdf']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
    if file.size > max_size_mb * 1024 * 1024:
        return False, f"File size exceeds {max_size_mb}MB"
    return True, "File is valid"

def generate_report_preview_url(report):
    return '/static/images/default-report-preview.png'

def add_watermark_to_pdf(input_path, user):
    try:
        output_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'watermarked_{os.path.basename(input_path)}')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create watermark PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        watermark_text = settings.WATERMARK_TEXT_TEMPLATE.format(
            user_name=user.username,
            user_email=user.email
        )
        c.setFont("Helvetica", 40)
        c.setFillColorRGB(0.8, 0.8, 0.8, alpha=0.3)
        c.translate(300, 400)
        c.rotate(45)
        c.drawCentredString(0, 0, watermark_text)
        c.showPage()
        c.save()
        watermark_pdf = buffer.getvalue()
        buffer.close()
        
        # Merge watermark with input PDF
        input_pdf = PyPDF2.PdfReader(input_path)
        watermark_pdf_reader = PyPDF2.PdfReader(BytesIO(watermark_pdf))
        output_pdf = PyPDF2.PdfWriter()
        
        for page in input_pdf.pages:
            page.merge_page(watermark_pdf_reader.pages[0])
            output_pdf.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            output_pdf.write(output_file)
        
        return output_path
    except Exception as e:
        logger.error(f"Error adding watermark to PDF: {str(e)}")
        raise
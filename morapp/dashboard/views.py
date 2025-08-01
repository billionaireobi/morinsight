from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count
from django.http import HttpResponse, Http404, FileResponse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import stripe
import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import os
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO
import PyPDF2
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from website.models import Report, ReportCategory, Order, OrderItem, Transaction, PurchasedReport, UserProfile
from .serializers import (
    ReportSerializer, ReportCategorySerializer, OrderSerializer, OrderItemSerializer,
    TransactionSerializer, PurchasedReportSerializer, UserProfileSerializer,
    ReportDetailSerializer, ClientSummarySerializer, OrderSummarySerializer
)
from .utils import generate_order_number, generate_transaction_id, send_order_confirmation_email, send_payment_success_email, add_watermark_to_pdf
from .permissions import IsClientUser, IsManagementUser, HasPurchasedReport, CanManageReports

logger = logging.getLogger('dashboard')

# Payment gateway configurations
stripe.api_key = settings.STRIPE_SECRET_KEY

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

# ========================================
# CLIENT DASHBOARD VIEWS
# ========================================

class ClientDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientUser]
    
    def get(self, request):
        user = request.user
        purchased_reports = PurchasedReport.objects.filter(client=user)
        total_spent = Transaction.objects.filter(order__client=user, confirmed=True).aggregate(total=Sum('amount'))['total'] or 0
        recent_purchases = purchased_reports.order_by('-purchased_on')[:5]
        
        data = {
            'total_reports_purchased': purchased_reports.count(),
            'total_amount_spent': float(total_spent),
            'recent_purchases': PurchasedReportSerializer(recent_purchases, many=True).data,
            'available_categories': ReportCategorySerializer(ReportCategory.objects.all(), many=True).data
        }
        return Response(data)

class ReportListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Report.objects.filter(is_active=True)
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if category:
            queryset = queryset.filter(category__slug=category)
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except (ValueError, TypeError):
                pass
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except (ValueError, TypeError):
                pass
        
        return queryset.order_by('-created_at')

class ReportDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, report_id):
        report = get_object_or_404(Report, id=report_id, is_active=True)
        has_purchased = PurchasedReport.objects.filter(client=request.user, report=report).exists()
        serializer = ReportDetailSerializer(report, context={'request': request})
        data = serializer.data
        data['has_purchased'] = has_purchased
        return Response(data)

class CreateOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientUser]
    
    def post(self, request):
        serializer = OrderSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            order = serializer.save()
            send_order_confirmation_email(order)
            return Response({
                'order_id': order.id,
                'order_number': str(order.order_number),
                'total_price': float(order.total_price),
                'status': order.status
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProcessPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientUser]
    
    @method_decorator(csrf_exempt)
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, client=request.user)
        if order.status != 'pending':
            return Response({"error": "Order is not pending payment"}, status=status.HTTP_400_BAD_REQUEST)
        
        payment_method = request.data.get('payment_method')
        if not payment_method:
            return Response({"error": "Payment method is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if payment_method == 'mpesa':
                access_token = get_mpesa_access_token()
                timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
                password = generate_mpesa_password(timestamp)
                response = requests.post(
                    f"https://{settings.MPESA_ENVIRONMENT}.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
                    headers={'Authorization': f'Bearer {access_token}'},
                    json={
                        'BusinessShortCode': settings.MPESA_SHORTCODE,
                        'Password': password,
                        'Timestamp': timestamp,
                        'TransactionType': 'CustomerPayBillOnline',
                        'Amount': str(int(order.total_price)),
                        'PartyA': request.user.userprofile.phone or '254700000000',
                        'PartyB': settings.MPESA_SHORTCODE,
                        'PhoneNumber': request.user.userprofile.phone or '254700000000',
                        'CallBackURL': settings.MPESA_CALLBACK_URL,
                        'AccountReference': str(order.order_number),
                        'TransactionDesc': f'Payment for order {order.order_number}'
                    }
                )
                response_data = response.json()
                if response_data.get('ResponseCode') == '0':
                    transaction = Transaction.objects.create(
                        order=order,
                        transaction_id=response_data['CheckoutRequestID'],
                        amount=order.total_price,
                        payment_method='mpesa'
                    )
                    return Response({'message': 'Payment initiated', 'transaction_id': transaction.transaction_id})
                
            elif payment_method == 'stripe':
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(order.total_price * 100),
                    currency='kes',
                    payment_method=request.data.get('payment_method_id'),
                    confirm=True,
                    return_url=f'{settings.FRONTEND_URL}/payment/callback/stripe/'
                )
                transaction = Transaction.objects.create(
                    order=order,
                    transaction_id=payment_intent.id,
                    amount=order.total_price,
                    payment_method='card',
                    confirmed=True
                )
                order.status = 'paid'
                order.save()
                for item in order.items.all():
                    PurchasedReport.objects.get_or_create(client=request.user, report=item.report)
                send_payment_success_email(transaction)
                return Response({'message': 'Payment successful', 'transaction_id': transaction.transaction_id})
            
            elif payment_method == 'paystack':
                response = requests.post(
                    'https://api.paystack.co/transaction/initialize',
                    headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
                    json={
                        'email': request.user.email,
                        'amount': int(order.total_price * 100),
                        'reference': str(order.order_number),
                        'callback_url': f'{settings.FRONTEND_URL}/payment/callback/paystack/'
                    }
                )
                response_data = response.json()
                if response_data.get('status'):
                    transaction = Transaction.objects.create(
                        order=order,
                        transaction_id=response_data['data']['reference'],
                        amount=order.total_price,
                        payment_method='paystack'
                    )
                    return Response({
                        'message': 'Payment initiated',
                        'authorization_url': response_data['data']['authorization_url']
                    })
                
            return Response({'error': 'Invalid payment method'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Payment error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class MpesaCallbackView(APIView):
    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = request.data.get('Body', {}).get('stkCallback', {})
            transaction_id = data.get('CheckoutRequestID')
            result_code = data.get('ResultCode')
            
            if result_code == '0':
                transaction = Transaction.objects.get(transaction_id=transaction_id)
                transaction.confirmed = True
                transaction.paid_at = timezone.now()
                transaction.save()
                order = transaction.order
                order.status = 'paid'
                order.save()
                for item in order.items.all():
                    PurchasedReport.objects.get_or_create(client=order.client, report=item.report)
                send_payment_success_email(transaction)
                logger.info(f"M-Pesa payment confirmed: {transaction_id}")
            return Response({'status': 'ok'})
        except Exception as e:
            logger.error(f"M-Pesa callback error: {str(e)}")
            return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

class PaystackCallbackView(APIView):
    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = request.data
            reference = data.get('reference')
            
            response = requests.get(
                f'https://api.paystack.co/transaction/verify/{reference}',
                headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'}
            )
            response_data = response.json()
            
            if response_data.get('status') and response_data['data']['status'] == 'success':
                transaction = Transaction.objects.get(transaction_id=reference)
                transaction.confirmed = True
                transaction.paid_at = timezone.now()
                transaction.save()
                order = transaction.order
                order.status = 'paid'
                order.save()
                for item in order.items.all():
                    PurchasedReport.objects.get_or_create(client=order.client, report=item.report)
                send_payment_success_email(transaction)
                logger.info(f"Paystack payment confirmed: {reference}")
            return Response({'status': 'ok'})
        except Exception as e:
            logger.error(f"Paystack callback error: {str(e)}")
            return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

class MyPurchasesView(generics.ListAPIView):
    serializer_class = PurchasedReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return PurchasedReport.objects.filter(client=self.request.user).order_by('-purchased_on')

class SecureReportViewerView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPurchasedReport]
    
    def get(self, request, report_id):
        try:
            report = get_object_or_404(Report, id=report_id)
            file_path = add_watermark_to_pdf(report.file.path, request.user)
            if not os.path.exists(file_path):
                raise FileNotFoundError("Watermarked file not found")
            response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{report.title}.pdf"'
            response['X-Frame-Options'] = 'DENY'
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self';"
            )
            return response
        except FileNotFoundError as e:
            logger.error(f"File error in SecureReportViewerView: {str(e)}")
            return Response({'error': 'Unable to serve report: File not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in SecureReportViewerView: {str(e)}")
            return Response({'error': 'Unable to serve report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========================================
# ADMIN DASHBOARD VIEWS
# ========================================

class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagementUser]
    
    def get(self, request):
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)
        
        total_revenue = Transaction.objects.filter(confirmed=True).aggregate(total=Sum('amount'))['total'] or 0
        revenue_30_days = Transaction.objects.filter(confirmed=True, paid_at__date__gte=last_30_days).aggregate(total=Sum('amount'))['total'] or 0
        revenue_7_days = Transaction.objects.filter(confirmed=True, paid_at__date__gte=last_7_days).aggregate(total=Sum('amount'))['total'] or 0
        total_clients = UserProfile.objects.filter(profile_type='Client').count()
        new_clients_30_days = UserProfile.objects.filter(profile_type='Client', join_date__date__gte=last_30_days).count()
        total_reports = Report.objects.count()
        active_reports = Report.objects.filter(is_active=True).count()
        total_purchases = PurchasedReport.objects.count()
        recent_orders = Order.objects.filter(status='paid').order_by('-created_at')[:10]
        recent_clients = UserProfile.objects.filter(profile_type='Client').order_by('-join_date')[:10]
        top_reports = Report.objects.annotate(purchase_count=Count('purchasedreport')).order_by('-purchase_count')[:10]
        
        data = {
            'revenue': {
                'total': float(total_revenue),
                'last_30_days': float(revenue_30_days),
                'last_7_days': float(revenue_7_days)
            },
            'users': {
                'total_clients': total_clients,
                'new_clients_30_days': new_clients_30_days
            },
            'reports': {
                'total': total_reports,
                'active': active_reports,
                'total_purchases': total_purchases
            },
            'recent_orders': OrderSummarySerializer(recent_orders, many=True).data,
            'recent_clients': ClientSummarySerializer(recent_clients, many=True).data,
            'top_reports': ReportSerializer(top_reports, many=True, context={'request': request}).data
        }
        return Response(data)

class ManageReportsView(generics.ListCreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageReports]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = Report.objects.all()
        search = self.request.query_params.get('search')
        is_active = self.request.query_params.get('is_active')
        
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-created_at')

class ManageReportDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageReports]
    queryset = Report.objects.all()

class ManageCategoriesView(generics.ListCreateAPIView):
    serializer_class = ReportCategorySerializer
    permission_classes = [permissions.IsAuthenticated, CanManageReports]
    queryset = ReportCategory.objects.all()

class ManageOrdersView(generics.ListAPIView):
    serializer_class = OrderSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsManagementUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = Order.objects.all()
        status_filter = self.request.query_params.get('status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            try:
                queryset = queryset.filter(created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date())
            except ValueError:
                pass
        if end_date:
            try:
                queryset = queryset.filter(created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date())
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')

class ManageClientsView(generics.ListAPIView):
    serializer_class = ClientSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsManagementUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = UserProfile.objects.filter(profile_type='Client')
        search = self.request.query_params.get('search')
        
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset.order_by('-join_date')

class RevenueAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagementUser]
    
    def get(self, request):
        today = timezone.now().date()
        twelve_months_ago = today - timedelta(days=365)
        monthly_revenue = []
        
        for i in range(12):
            month_start = today.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            revenue = Transaction.objects.filter(
                confirmed=True,
                paid_at__date__range=[month_start, month_end]
            ).aggregate(total=Sum('amount'))['total'] or 0
            orders_count = Transaction.objects.filter(
                confirmed=True,
                paid_at__date__range=[month_start, month_end]
            ).count()
            reports_sold = PurchasedReport.objects.filter(
                purchased_on__date__range=[month_start, month_end]
            ).count()
            
            monthly_revenue.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': float(revenue),
                'orders_count': orders_count,
                'reports_sold': reports_sold
            })
        
        top_reports = Report.objects.annotate(
            purchase_count=Count('purchasedreport'),
            total_revenue=Sum('orderitem__price')
        ).order_by('-total_revenue')[:10]
        
        return Response({
            'monthly_revenue': list(reversed(monthly_revenue)),
            'top_reports': [
                {
                    'title': report.title,
                    'purchase_count': report.purchase_count,
                    'total_revenue': float(report.total_revenue or 0)
                }
                for report in top_reports
            ]
        })

class PublicReportsView(generics.ListAPIView):
    serializer_class = ReportSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = []  # No authentication required
    
    def get_queryset(self):
        queryset = Report.objects.filter(is_active=True)
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if category:
            queryset = queryset.filter(category__slug=category)
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except (ValueError, TypeError):
                pass
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except (ValueError, TypeError):
                pass
        
        return queryset.order_by('-created_at')

class PublicCategoriesView(generics.ListAPIView):
    serializer_class = ReportCategorySerializer
    permission_classes = []  # No authentication required
    queryset = ReportCategory.objects.all()

# Payment utility functions
def get_mpesa_access_token():
    try:
        response = requests.get(
            f"https://{settings.MPESA_ENVIRONMENT}.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        logger.error(f"M-Pesa access token error: {str(e)}")
        raise

def generate_mpesa_password(timestamp):
    import base64
    data = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(data.encode()).decode()
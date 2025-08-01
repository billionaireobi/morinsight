
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('client/', views.ClientDashboardView.as_view(), name='client_dashboard'),
    path('admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<int:report_id>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('orders/create/', views.CreateOrderView.as_view(), name='create_order'),
    path('orders/<int:order_id>/pay/', views.ProcessPaymentView.as_view(), name='process_payment'),
    path('purchases/', views.MyPurchasesView.as_view(), name='my_purchases'),
    path('reports/<int:report_id>/viewer/', views.SecureReportViewerView.as_view(), name='secure_viewer'),
    path('mpesa/callback/', views.MpesaCallbackView.as_view(), name='mpesa_callback'),
    path('paystack/callback/', views.PaystackCallbackView.as_view(), name='paystack_callback'),
    path('admin/reports/', views.ManageReportsView.as_view(), name='manage_reports'),
    path('admin/reports/<int:pk>/', views.ManageReportDetailView.as_view(), name='manage_report_detail'),
    path('admin/orders/', views.ManageOrdersView.as_view(), name='manage_orders'),
    path('admin/categories/', views.ManageCategoriesView.as_view(), name='manage_categories'),
    path('admin/clients/', views.ManageClientsView.as_view(), name='manage_clients'),
    path('admin/revenue/', views.RevenueAnalyticsView.as_view(), name='revenue_analytics'),
    path('public/reports/', views.PublicReportsView.as_view(), name='public_reports'),
    path('public/categories/', views.PublicCategoriesView.as_view(), name='public_categories'),
]
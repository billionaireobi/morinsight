from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone
from website.models import Report, ReportCategory, Order, OrderItem, Transaction, PurchasedReport, UserProfile
from morapp.utils import generate_order_number  # Import from morapp.utils

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'date_joined']
        read_only_fields = ['id', 'username', 'date_joined']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_purchases = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = ['user', 'phone', 'profile_type', 'join_date', 'gender', 'total_purchases', 'total_spent']
        read_only_fields = ['join_date', 'total_purchases', 'total_spent']
    
    def get_total_purchases(self, obj):
        return PurchasedReport.objects.filter(client=obj.user).count() if obj.is_client() else 0
    
    def get_total_spent(self, obj):
        if obj.is_client():
            total = Transaction.objects.filter(order__client=obj.user, confirmed=True).aggregate(total=Sum('amount'))['total']
            return float(total) if total else 0
        return 0

class ReportCategorySerializer(serializers.ModelSerializer):
    report_count = serializers.SerializerMethodField()  # Fixed typo: TranserializerMethodField -> SerializerMethodField
    
    class Meta:
        model = ReportCategory
        fields = ['id', 'name', 'slug', 'report_count']
        read_only_fields = ['slug']
    
    def get_report_count(self, obj):
        return obj.report_set.filter(is_active=True).count()

class ReportSerializer(serializers.ModelSerializer):
    category = ReportCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    purchase_count = serializers.SerializerMethodField()
    preview_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = ['id', 'title', 'description', 'category', 'category_id', 'price', 
                 'preview_image', 'preview_image_url', 'created_at', 'updated_at', 'is_active', 'purchase_count']
        read_only_fields = ['id', 'created_at', 'updated_at', 'purchase_count']
    
    def get_purchase_count(self, obj):
        return PurchasedReport.objects.filter(report=obj).count()
    
    def get_preview_image_url(self, obj):
        if obj.preview_image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.preview_image.url) if request else obj.preview_image.url
        return None
    
    def validate_category_id(self, value):
        if value and not ReportCategory.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid category ID")
        return value
    
    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category'] = ReportCategory.objects.get(id=category_id)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        category_id = validated_data.pop('category_id', None)
        if category_id is not None:
            validated_data['category'] = ReportCategory.objects.get(id=category_id) if category_id else None
        return super().update(instance, validated_data)

class ReportDetailSerializer(ReportSerializer):
    file_size = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    
    class Meta(ReportSerializer.Meta):
        fields = ReportSerializer.Meta.fields + ['file_size', 'file_name']
    
    def get_file_size(self, obj):
        return obj.file.size if obj.file else None
    
    def get_file_name(self, obj):
        return obj.file.name.split('/')[-1] if obj.file else None

class OrderItemSerializer(serializers.ModelSerializer):
    report = ReportSerializer(read_only=True)
    report_title = serializers.CharField(source='report.title', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'report', 'report_title', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    report_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'client', 'status', 'total_price', 'created_at', 'items', 'item_count', 'report_ids']
        read_only_fields = ['id', 'order_number', 'created_at', 'items', 'item_count']
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def create(self, validated_data):
        report_ids = validated_data.pop('report_ids', [])
        reports = Report.objects.filter(id__in=report_ids, is_active=True)
        if len(reports) != len(report_ids):
            raise serializers.ValidationError("Some reports are invalid or unavailable")
        
        already_owned = PurchasedReport.objects.filter(client=self.context['request'].user, report__in=reports).values_list('report__title', flat=True)
        if already_owned:
            raise serializers.ValidationError(f"You already own: {', '.join(already_owned)}")
        
        total_price = sum(report.price for report in reports)
        order = Order.objects.create(
            client=self.context['request'].user,
            total_price=total_price,
            order_number=generate_order_number()
        )
        
        for report in reports:
            OrderItem.objects.create(order=order, report=report, price=report.price, quantity=1)
        
        return order

class TransactionSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'order', 'transaction_id', 'amount', 'payment_method', 'paid_at', 'confirmed']
        read_only_fields = ['id', 'paid_at', 'transaction_id', 'confirmed']

class PurchasedReportSerializer(serializers.ModelSerializer):
    report = ReportSerializer(read_only=True)
    client = UserSerializer(read_only=True)
    days_since_purchase = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchasedReport
        fields = ['id', 'client', 'report', 'purchased_on', 'days_since_purchase']
        read_only_fields = ['id', 'purchased_on']
    
    def get_days_since_purchase(self, obj):
        delta = timezone.now() - obj.purchased_on
        return delta.days

class ClientSummarySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    recent_purchase = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = ['user', 'join_date', 'recent_purchase']
    
    def get_recent_purchase(self, obj):
        if obj.is_client():
            recent = PurchasedReport.objects.filter(client=obj.user).order_by('-purchased_on').first()
            if recent:
                return {'report_title': recent.report.title, 'purchased_on': recent.purchased_on}
        return None

class OrderSummarySerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'client_name', 'client_email', 'status', 'total_price', 'created_at']

class RevenueAnalyticsSerializer(serializers.Serializer):
    period = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    orders_count = serializers.IntegerField()
    reports_sold = serializers.IntegerField()

class DashboardStatsSerializer(serializers.Serializer):
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_clients = serializers.IntegerField()
    total_reports = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    new_clients_this_month = serializers.IntegerField()
    pending_orders = serializers.IntegerField()

class ReportValidationMixin:
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        if value > 1000000:
            raise serializers.ValidationError("Price cannot exceed 1,000,000")
        return value
    
    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        return value.strip()

class OrderValidationMixin:
    def validate_total_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Total price cannot be negative")
        return value

class ReportCreateUpdateSerializer(ReportValidationMixin, ReportSerializer):
    pass

class OrderCreateSerializer(OrderValidationMixin, OrderSerializer):
    pass
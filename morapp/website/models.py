from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from morapp.utils import generate_order_number  # Import from morapp.utils

# ========================
# USER PROFILE
# ========================
class UserProfile(models.Model):
    PROFILE_TYPE_CHOICES = [
        ('Management', 'Management'),
        ('Client', 'Client'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    date_modified = models.DateTimeField(auto_now=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_type = models.CharField(max_length=50, choices=PROFILE_TYPE_CHOICES, default='Client')
    join_date = models.DateTimeField(default=timezone.now)
    gender = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return self.user.username

    def is_management(self):
        return self.profile_type == 'Management'

    def is_client(self):
        return self.profile_type == 'Client'

    class Meta:
        permissions = [
            ("can_change_profile_type", "Can change profile type field"),
        ]

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Automatically create a profile & assign group when a new user is created"""
    if created:
        profile_type = 'Management' if instance.is_superuser else 'Client'
        profile = UserProfile.objects.create(user=instance, profile_type=profile_type)
        group = Group.objects.get_or_create(name=profile_type)[0]
        instance.groups.add(group)

# ========================
# REPORT CATEGORY
# ========================
class ReportCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# ========================
# REPORT MODEL
# ========================
class Report(models.Model):
    """
    Represents a digital report (the product).
    Includes:
      - Preview (blurred image)
      - Full locked file
    """
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField()
    category = models.ForeignKey(ReportCategory, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    preview_image = models.ImageField(upload_to='report_previews/', blank=True, null=True)
    file = models.FileField(upload_to='reports/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

# ========================
# ORDER MODEL
# ========================
class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )

    client = models.ForeignKey(User, on_delete=models.CASCADE)
    order_number = models.CharField(max_length=16, unique=True, default=generate_order_number)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_number} - {self.client.username}"

# ========================
# ORDER ITEM
# ========================
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    report = models.ForeignKey(Report, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.report.title} (x{self.quantity})"

# ========================
# TRANSACTION MODEL
# ========================
class Transaction(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank', 'Bank Transfer'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    paid_at = models.DateTimeField(auto_now_add=True)
    confirmed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.transaction_id} - {self.amount}"

# ========================
# PURCHASED REPORTS (Access Control)
# ========================
class PurchasedReport(models.Model):
    """
    Tracks which clients have purchased which reports.
    Used to unlock secure viewing of the report.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    report = models.ForeignKey(Report, on_delete=models.CASCADE)
    purchased_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'report')

    def __str__(self):
        return f"{self.client.username} purchased {self.report.title}"
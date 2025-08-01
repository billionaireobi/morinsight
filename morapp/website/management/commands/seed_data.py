from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from website.models import (
    ReportCategory, Report, Order, OrderItem, Transaction, PurchasedReport
)
from django.core.files.base import ContentFile
from decimal import Decimal
import random

class Command(BaseCommand):
    help = "Seed the database with sample data for testing API endpoints"

    def handle(self, *args, **kwargs):
        # ✅ 1. Create Admin & Client Users
        admin, created = User.objects.get_or_create(
            username="admin",
            email="admin@example.com",
            is_staff=True,
            is_superuser=True
        )
        if created:
            admin.set_password("AdminPass123")
            admin.save()
            self.stdout.write(self.style.SUCCESS("✅ Admin user created (admin@example.com / AdminPass123)"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Admin user already exists"))

        client, created = User.objects.get_or_create(
            username="client",
            email="client@example.com",
            is_staff=False,
            is_superuser=False
        )
        if created:
            client.set_password("ClientPass123")
            client.save()
            self.stdout.write(self.style.SUCCESS("✅ Client user created (client@example.com / ClientPass123)"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Client user already exists"))

        # ✅ 2. Create Categories
        categories = ["Banking", "Technology", "Healthcare", "Retail"]
        category_objs = []
        for cat_name in categories:
            category, _ = ReportCategory.objects.get_or_create(name=cat_name)
            category_objs.append(category)
        self.stdout.write(self.style.SUCCESS(f"✅ {len(categories)} categories created"))

        # ✅ 3. Create Reports (with dummy file)
        reports = [
            {"title": "Mobile Banking in Kenya 2025", "category": category_objs[0], "price": 2000},
            {"title": "AI Trends in 2025", "category": category_objs[1], "price": 3500},
            {"title": "Healthcare Innovations 2025", "category": category_objs[2], "price": 4000},
            {"title": "Retail Market Analysis 2025", "category": category_objs[3], "price": 2500},
        ]

        report_objs = []
        for rpt in reports:
            report, created = Report.objects.get_or_create(
                title=rpt["title"],
                category=rpt["category"],
                price=Decimal(rpt["price"]),
                description="This is a sample report description."
            )
            if created:
                report.file.save(f"{report.slug}.txt", ContentFile(b"Sample report content"))
            report_objs.append(report)
        self.stdout.write(self.style.SUCCESS(f"✅ {len(report_objs)} reports created"))

        # ✅ 4. Create Orders for the Client
        for i in range(2):  # create 2 orders
            order = Order.objects.create(
                client=client,
                status="paid",
                total_price=0
            )
            total_price = Decimal(0)
            for report in random.sample(report_objs, 2):  # each order has 2 reports
                item = OrderItem.objects.create(
                    order=order,
                    report=report,
                    quantity=1,
                    price=report.price
                )
                total_price += report.price

                # ✅ Mark report as purchased
                PurchasedReport.objects.get_or_create(client=client, report=report)

            # ✅ Update order total
            order.total_price = total_price
            order.save()

            # ✅ Add Transaction
            Transaction.objects.create(
                order=order,
                transaction_id=f"TXN{i+1:03}",
                amount=total_price,
                payment_method="mpesa",
                confirmed=True
            )
        self.stdout.write(self.style.SUCCESS("✅ Orders, Items, Transactions, and PurchasedReports created"))

        self.stdout.write(self.style.SUCCESS("🎉 Database seeding completed successfully!"))

from django.core.management.base import BaseCommand
from dashboard.cleanup import cleanup_expired_orders, cleanup_temp_files, generate_monthly_report
from django.utils import timezone

class Command(BaseCommand):
    help = 'Runs cleanup tasks and monthly report generation'

    def handle(self, *args, **kwargs):
        self.stdout.write("Running cleanup tasks...")
        cleanup_expired_orders()
        cleanup_temp_files()
        if timezone.now().day == 1:
            generate_monthly_report()
        self.stdout.write(self.style.SUCCESS("Cleanup tasks completed"))
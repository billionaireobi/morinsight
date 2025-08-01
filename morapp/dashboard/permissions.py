from rest_framework import permissions
from website.models import UserProfile, PurchasedReport

class IsClientUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'userprofile') and request.user.userprofile.profile_type == 'Client'

class IsManagementUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            (hasattr(request.user, 'userprofile') and request.user.userprofile.profile_type == 'Management')
        )

class HasPurchasedReport(permissions.BasePermission):
    def has_permission(self, request, view):
        report_id = view.kwargs.get('report_id')
        if not report_id:
            return False
        return PurchasedReport.objects.filter(client=request.user, report_id=report_id).exists()

class CanManageReports(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            (hasattr(request.user, 'userprofile') and request.user.userprofile.profile_type == 'Management')
        )
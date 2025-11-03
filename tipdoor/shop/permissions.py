from rest_framework.permissions import BasePermission
from vendors.models import Vendor

class IsVendor(BasePermission):
    def has_permission(self, request, view):
        # Allow authenticated users with an active Vendor profile
        return request.user.is_authenticated and hasattr(request.user, 'vendor') and request.user.vendor.is_active

    def has_object_permission(self, request, view, obj):
        # Only allow access to the vendor's own products
        return obj.vendor == request.user.vendor

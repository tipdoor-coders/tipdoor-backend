from rest_framework import permissions

class IsAssignedDeliveryPartner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Allow only the assigned delivery partner or staff to modify the object
        return obj.delivery_partner.user == request.user or request.user.is_staff

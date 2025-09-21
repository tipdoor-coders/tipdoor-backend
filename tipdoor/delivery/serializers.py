from rest_framework import serializers
from .models import DeliveryPartner, DeliveryAssignment
from shop.serializers import OrderSerializer

class DeliveryPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPartner
        fields = ['id', 'name', 'phone', 'vehicle_type', 'is_available', 'service_area']

class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    delivery_partner = DeliveryPartnerSerializer(read_only=True)

    class Meta:
        model = DeliveryAssignment
        fields = ['id', 'order', 'delivery_partner', 'status', 'assigned_at', 'estimated_delivery_time']

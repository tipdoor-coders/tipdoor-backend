from django.db import models
from django.contrib.auth.models import User
from shop.models import Order


class DeliveryPartner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    vehicle_type = models.CharField(max_length=50, choices=[
        ('BIKE', 'Bike'),
        ('CAR', 'Car'),
        ('VAN', 'Van'),
    ])
    is_available = models.BooleanField(default=True)
    service_area = models.CharField(max_length=200)  # Could use GIS fields for precise geolocation
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class DeliveryAssignment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    delivery_partner = models.ForeignKey(DeliveryPartner, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, choices=[
        ('ASSIGNED', 'Assigned'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
    ])
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.order} - {self.delivery_partner}"

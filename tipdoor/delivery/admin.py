from django.contrib import admin

from .models import DeliveryPartner, DeliveryAssignment

admin.site.register(DeliveryPartner)
admin.site.register(DeliveryAssignment)

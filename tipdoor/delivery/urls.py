from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryPartnerViewSet, DeliveryAssignmentViewSet

router = DefaultRouter()
router.register(r'delivery-partners', DeliveryPartnerViewSet)
router.register(r'delivery-assignments', DeliveryAssignmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import DeliveryPartner, DeliveryAssignment
from .serializers import DeliveryPartnerSerializer, DeliveryAssignmentSerializer

class DeliveryPartnerViewSet(viewsets.ModelViewSet):
    queryset = DeliveryPartner.objects.all()
    serializer_class = DeliveryPartnerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Restrict delivery partners to see only their own profile
        if not self.request.user.is_staff:
            return DeliveryPartner.objects.filter(user=self.request.user)
        return DeliveryPartner.objects.all()

class DeliveryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DeliveryAssignment.objects.all()
    serializer_class = DeliveryAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Delivery partners see only their assignments
        if not self.request.user.is_staff:
            return DeliveryAssignment.objects.filter(delivery_partner__user=self.request.user)
        return DeliveryAssignment.objects.all()

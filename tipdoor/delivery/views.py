from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .models import DeliveryPartner, DeliveryAssignment
from .serializers import DeliveryPartnerSerializer, DeliveryAssignmentSerializer
from .permissions import IsAssignedDeliveryPartner

@extend_schema(tags=["Delivery"])
class DeliveryPartnerViewSet(viewsets.ModelViewSet):
    queryset = DeliveryPartner.objects.all()
    serializer_class = DeliveryPartnerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Restrict delivery partners to see only their own profile
        if not self.request.user.is_staff:
            return DeliveryPartner.objects.filter(user=self.request.user)
        return DeliveryPartner.objects.all()

@extend_schema(tags=["Delivery"])
class DeliveryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DeliveryAssignment.objects.all()
    serializer_class = DeliveryAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAssignedDeliveryPartner]

    def get_queryset(self):
        # Delivery partners see only their assignments
        if not self.request.user.is_staff:
            return DeliveryAssignment.objects.filter(delivery_partner__user=self.request.user)
        return DeliveryAssignment.objects.all()

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        assignment = self.get_object()
        new_status = request.data.get('status')

        # Restrict status updates to ASSIGNED or DELIVERED
        allowed_statuses = ['ASSIGNED', 'DELIVERED']
        if not new_status:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status not in allowed_statuses:
            return Response(
                {'error': f'Invalid status. Allowed choices: {allowed_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optional: Add business logic for valid transitions
        # E.g., Only allow ASSIGNED -> DELIVERED
        if assignment.status == 'DELIVERED':
            return Response(
                {'error': 'Cannot change status of a delivered order'},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment.status = new_status
        assignment.save()

        # Optionally update the Order status to align with DeliveryAssignment
        if new_status == 'DELIVERED':
            assignment.order.status = 'DELIVERED'
            assignment.order.save()

        return Response(
            {'message': f'Assignment status updated to {new_status}'},
            status=status.HTTP_200_OK
        )

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from .models import Vendor
from .serializers import VendorSerializer

@extend_schema(tags=["Vendor"])
class VendorRegisterView(generics.CreateAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated users to register

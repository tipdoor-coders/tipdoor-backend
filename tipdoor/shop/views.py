from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import generics, status, views
from .models import Cart, CartItem, Product, Order, OrderItem, Promotion
from vendors.models import Vendor
from delivery.models import DeliveryPartner
from .serializers import ProductSerializer, CartSerializer, CartItemSerializer, OrderSerializer, OrderItemSerializer, PromotionSerializer, CustomerRegistrationSerializer, CustomerSerializer, OrderStatusUpdateSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.serializers import Serializer, CharField
from django.db.models import Q
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from .permissions import IsVendor
from django.utils import timezone
from . import serializers
from django.core.exceptions import ValidationError
from utils.mixins import CartMixin

class CustomerProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(is_published=True)

class LatestArrivalView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(is_published=True).order_by('-created_at')[:5]

class CartView(CartMixin, generics.RetrieveAPIView):
    """Gets the user's cart"""

    serializer_class = CartSerializer

    def get_object(self):
        return self.get_cart(self.request)

class AddToCartView(CartMixin, APIView):
    """Adds an item to the cart"""

    serializer_class = serializers.AddToCartSerializer

    def post(self, request):
        input_serializer = self.serializer_class(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        product_id = input_serializer.validated_data['product_id']
        quantity = input_serializer.validated_data['quantity']

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        cart = self.get_cart(request)

        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={'quantity': quantity}
        )
        if not item_created:
            cart_item.quantity += quantity
            cart_item.save()
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class UpdateCartItemView(CartMixin, APIView):
    """Updates the quantity of an item in the user's cart"""

    serializer_class = serializers.UpdateCartItemSerializer

    def patch(self, request, item_id):
        input_serializer = self.serializer_class(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        quantity = input_serializer.validated_data['quantity']

        cart = self.get_cart(request)

        try:
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            cart_item.quantity = quantity
            cart_item.save()
            serializer = CartSerializer(cart, context={'request': request})
            return Response(serializer.data)

        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

class RemoveCartItemView(CartMixin, APIView):
    """Remove an item from the cart"""

    serializer_class = CartSerializer

    def delete(self, request, item_id):
        cart = self.get_cart(request)

        try:
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            cart_item.delete()
            serializer = CartSerializer(cart, context={'request': request})
            return Response(serializer.data)

        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

class CustomerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.customer

class ProductSearchView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = Product.objects.filter(Q(name__icontains=query), is_published=True)
        else:
            return Product.objects.none()
        return queryset

class CustomerRegisterView(generics.CreateAPIView):
    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny]

class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def post(self, request):
        shipping_address = request.data.get('shippingAddress', {})
        promo_code = request.data.get('promo_code', '')

        self._validate_shipping(shipping_address)

        cart_user, created = Cart.objects.get_or_create(customer=request.user.customer)
        cart_items = CartItem.objects.filter(cart=cart_user)

        if not cart_items:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        promotion = self._get_valid_promotion(promo_code, cart_items)

        with transaction.atomic():
            try:
                total_amount = sum(item.product.price * item.quantity for item in cart_items)
                discounted_total = total_amount
                order_items_data = []

                for item in cart_items:
                    price = item.product.price
                    discounted_price = price
                    if promotion and promotion.applicable_products.filter(id=item.product.id).exists():
                        if promotion.discount_type == 'percentage':
                            discounted_price = price * (1 - promotion.discount_value / 100)
                        elif promotion.discount_type == 'fixed':
                            discounted_price = max(0, price - promotion.discount_value)
                    discounted_total -= (price - discounted_price) * item.quantity
                    order_items_data.append({
                        'product': item.product,
                        'quantity': item.quantity,
                        'price': price,
                        'discounted_price': discounted_price
                    })

                order = Order.objects.create(
                    user=request.user.customer,
                    address=shipping_address['address'],
                    city=shipping_address['city'],
                    postal_code=shipping_address['postal_code'],
                    country=shipping_address['country'],
                    total_amount=total_amount,
                    promo_code=promo_code if promotion else None,
                    status='Pending'
                )

                for item_data in order_items_data:
                    OrderItem.objects.create(
                        order=order,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        price=item_data['price'],
                        discounted_price=item_data['discounted_price'] if item_data['discounted_price'] != item_data['price'] else None
                    )

                cart_items.delete()  # Clear cart after order

                serializer = OrderSerializer(order, context={'request': request, 'promo_code': promo_code})
                response_data = serializer.data
                response_data['order_id'] = order.id
                response_data['message'] = 'Order created successfully'

                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _validate_shipping(self, shipping_address):
        if not all([
            shipping_address.get('address'),
            shipping_address.get('city'),
            shipping_address.get('postal_code'),
            shipping_address.get('country'),
        ]):
            raise ValidationError('All fields are required')

    def _get_valid_promotion(self, promo_code, cart_items):
        if not promo_code:
            return None
        now = timezone.now()
        try:
            promotion = Promotion.objects.get(
                promo_code=promo_code,
                is_active=True,
                start_date__lte=now,
                end_date__gte=now
            )
        except Promotion.DoesNotExist:
            raise ValidationError('Invalid or inactive promo code')

        applicable = any(
            promotion.applicable_products.filter(id=item.product.id).exists()
            for item in cart_items
        )
        if not applicable:
            raise ValidationError('Promo code does not apply to any items in the cart')

        return promotion

class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        customer = getattr(self.request.user, 'customer', None)
        if not customer:
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user.customer).order_by('-created_at')

class ProductPublishView(views.APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            if not IsVendor().has_object_permission(request, self, product):
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            product.is_published = True
            product.save()
            return Response({'message': 'Product published'}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

class ProductUnpublishView(views.APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            if not IsVendor().has_object_permission(request, self, product):
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            product.is_published = False
            product.save()
            return Response({'message': 'Product unpublished'}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        return Product.objects.filter(is_published=True)

class VendorProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsVendor]
    lookup_field = 'pk'

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user.vendor)

class VendorProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user.vendor)

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor)

class VendorOrderItemListView(generics.ListAPIView):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        return OrderItem.objects.filter(product__vendor__user=self.request.user).select_related('order', 'product')

    def get_serializer_context(self):
        return {'request': self.request}

class VendorOrderStatusUpdateView(generics.GenericAPIView):
    """
    Allows a vendor to update the status of an order that contains their products.
    If the order is approved, available delivery partners are notified.
    """

    permission_classes = [IsAuthenticated, IsVendor]
    serializer_class = OrderStatusUpdateSerializer

    def post(self, request, order_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response(
                {"error": "Vendor profile not found"},
                status=status.HTTP_403_FORBIDDEN
            )

        has_items = OrderItem.objects.filter(order=order, product__vendor=vendor).exists()
        if not has_items:
            return Response(
                {"error": "You do not have any items in this order"},
                status=status.HTTP_403_FORBIDDEN
            )

        order.status = new_status
        order.save(update_fields=["status"])

        if new_status == "APPROVED":
            active_partners = DeliveryPartner.objects.filter(
                is_available=True,
                service_area__contains=order.address
            )
            for partner in active_partners:
                send_notification(partner, order)

        return Response(
            {"message": f"Order status updated to {new_status}"},
            status=status.HTTP_200_OK
        )

class VendorPromotionListCreateView(generics.ListCreateAPIView):
    serializer_class = PromotionSerializer
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        return Promotion.objects.filter(vendor__user=self.request.user)

    def perform_create(self, serializer):
        vendor = Vendor.objects.get(user=self.request.user)
        serializer.save(vendor=vendor)

    def get_serializer_context(self):
        return {'request': self.request}

class VendorPromotionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PromotionSerializer
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        return Promotion.objects.filter(vendor__user=self.request.user)

    def get_serializer_context(self):
        return {'request': self.request}

def index(request):
    return HttpResponse("Hello, world. You're at shop.")

def send_notification(partner, order):
    print("Send notification function")

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


class CustomerProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(is_published=True)

class LatestArrivalView(generics.ListAPIView):
    queryset = Product.objects.order_by('-created_at')[:5]  # Newest 5 products
    serializer_class = ProductSerializer

    def get_serializer_context(self):
        return {'request': self.request}

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(customer=request.user.customer)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        try:
            product = Product.objects.get(id=product_id)
            cart, created = Cart.objects.get_or_create(customer=request.user.customer)
            cart_item, item_created = CartItem.objects.get_or_create(
                cart=cart, product=product, defaults={'quantity': quantity}
            )
            if not item_created:
                cart_item.quantity += int(quantity)
                cart_item.save()
            serializer = CartSerializer(cart, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__customer=request.user.customer)
            quantity = request.data.get('quantity')
            if quantity is None or int(quantity) < 1:
                return Response({"error": "Quantity must be at least 1"}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity = int(quantity)
            cart_item.save()
            serializer = CartSerializer(cart_item.cart, context={'request': request})
            return Response(serializer.data)

        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

class RemoveCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__customer=request.user.customer)
            cart = cart_item.cart
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

class ProductSearchView(APIView):
    def get(self, request):
        query = request.GET.get('q', '')
        if not query:
            return Response([], status=status.HTTP_200_OK)
        
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(price__icontains=query)
        )
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class CustomerRegisterView(generics.CreateAPIView):
    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny]

class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        shipping_address = request.data.get('shippingAddress', {})
        payment_info = request.data.get('paymentInfo', {})
        promo_code = request.data.get('promo_code', '')
        
        if not all([
            shipping_address.get('address'),
            shipping_address.get('city'),
            shipping_address.get('postal_code'),
            shipping_address.get('country'),
            payment_info.get('card_number'),
            payment_info.get('expiry'),
            payment_info.get('cvv'),
        ]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        cart_user, created = Cart.objects.get_or_create(customer=request.user.customer)
        cart_items = CartItem.objects.filter(cart=cart_user)

        if not cart_items:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        promotion = None
        if promo_code:
            try:
                now = timezone.now()
                promotion = Promotion.objects.get(
                    promo_code=promo_code,
                    is_active=True,
                    start_date__lte=now,
                    end_date__gte=now
                )
                # Check if promo applies to any cart items
                applicable = any(promotion.applicable_products.filter(id=item.product.id).exists() for item in cart_items)
                if not applicable:
                    return Response({'error': 'Promo code does not apply to any items in the cart'}, status=status.HTTP_400_BAD_REQUEST)
            except Promotion.DoesNotExist:
                return Response({'error': 'Invalid or inactive promo code'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            total_amount = sum(item.product.price * item.quantity for item in cart_items)
            discounted_total = float(total_amount)
            order_items_data = []

            for item in cart_items:
                price = float(item.product.price)
                discounted_price = price
                if promotion and promotion.applicable_products.filter(id=item.product.id).exists():
                    if promotion.discount_type == 'percentage':
                        discounted_price = float(price) * (1 - float(promotion.discount_value) / 100)
                    elif promotion.discount_type == 'fixed':
                        discounted_price = max(0, price - float(promotion.discount_value))
                discounted_total -= (price - discounted_price) * float(item.quantity)
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

            return Response({'message': 'Order created successfully', 'order_id': order.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user.customer).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

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

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        # Vendors see only their products; customers see published products
        if self.request.user.is_authenticated and hasattr(self.request.user, 'vendor') and self.request.user.vendor.is_active:
            return Product.objects.filter(vendor__user=self.request.user)
        return Product.objects.filter(is_published=True)

class VendorProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        return Product.objects.filter(vendor__user=self.request.user)

    def perform_create(self, serializer):
        vendor = Vendor.objects.get(user=self.request.user)
        serializer.save(vendor=vendor)

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

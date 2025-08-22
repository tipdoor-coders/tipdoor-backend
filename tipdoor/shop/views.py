from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import generics
from .models import Cart, CartItem, Product, Order, OrderItem
from .serializers import ProductSerializer, CartSerializer, CartItemSerializer, OrderSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import Serializer, CharField
from django.db.models import Q
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction


class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):

        return {'request': self.request}

class LatestArrivalView(generics.ListAPIView):
    queryset = Product.objects.order_by('-created_at')[:5]  # Newest 5 products
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        return {'request': self.request}

class CartView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        try:
            product = Product.objects.get(id=product_id)
            cart, created = Cart.objects.get_or_create(user=request.user)
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
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
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
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
            cart = cart_item.cart
            cart_item.delete()
            serializer = CartSerializer(cart, context={'request': request})
            return Response(serializer.data)

        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    class UserSerializer(Serializer):
        username = CharField()
        email = CharField()

    def get(self, request):
        serializer = self.UserSerializer(request.user)
        return Response(serializer.data)

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

class RegisterView(APIView):
    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not all([username, email, password]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'User created successfully'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProductDetailView(APIView):
    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            serializer = ProductSerializer(product, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        shipping_address = request.data.get('shipping_address', {})
        payment_info = request.data.get('payment_info', {})
        
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
        
        # cart_items = CartItem.objects.filter(user=request.user)
        cart_user, created = Cart.objects.get_or_create(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart_user)

        if not cart_items:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            total_amount = sum(item.product.price * item.quantity for item in cart_items)
            order = Order.objects.create(
                user=request.user,
                address=shipping_address['address'],
                city=shipping_address['city'],
                postal_code=shipping_address['postal_code'],
                country=shipping_address['country'],
                total_amount=total_amount,
                status='Pending'
            )
            
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            
            cart_items.delete()  # Clear cart after order
            return Response({'message': 'Order created successfully', 'order_id': order.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

def index(request):
    return HttpResponse("Hello, world. You're at shop.")


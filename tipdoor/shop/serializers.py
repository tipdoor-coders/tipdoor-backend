from rest_framework import serializers
from django.conf import settings
from .models import Product, Cart, CartItem, OrderItem, Order

class ProductSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)  # Derived from stock

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else f"{settings.MEDIA_URL}{obj.image}".lstrip('/')
        return None

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'price', 'stock', 'status', 'image', 'is_published', 'created_at', 'updated_at', 'vendor']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at','vendor']

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'created_at', 'items']

class OrderItemSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    order_date = serializers.DateTimeField(source='order.created_at', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    customer_name = serializers.CharField(source='order.user.get_full_name', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'order_id', 'order_date', 'product_name', 'product_sku', 'quantity', 'price', 'customer_name', 'order_status']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'created_at', 'address', 'city', 'postal_code', 'country', 'total_amount', 'status', 'items']

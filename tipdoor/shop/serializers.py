from rest_framework import serializers
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Product, Cart, CartItem, OrderItem, Order, Promotion, Vendor, Customer

class ProductSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)  # Derived from stock
    promotion = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else f"{settings.MEDIA_URL}{obj.image}".lstrip('/')
        return None

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'price', 'stock', 'status', 'image', 'is_published', 'created_at', 'updated_at', 'vendor', 'promotion', 'discounted_price']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at','vendor', 'promotion', 'discounted_price']

    def get_promotion(self, obj):
        # Get active promotions for this product
        now = timezone.now()
        promotion = Promotion.objects.filter(
            applicable_products__id=obj.id,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()
        if promotion:
            return {
                'title': promotion.title,
                'promo_code': promotion.promo_code,
                'discount_type': promotion.discount_type,
                'discount_value': float(promotion.discount_value),
            }
        return None

    def get_discounted_price(self, obj):
        now = timezone.now()
        promotion = Promotion.objects.filter(
            applicable_products__id=obj.id,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()
        if promotion:
            price = float(obj.price)
            if promotion.discount_type == 'percentage':
                return price * (1 - float(promotion.discount_value) / 100) 
            elif promotion.discount_type == 'fixed':
                return max(0, price - float(promotion.discount_value))
        return None

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = Customer
        fields = ['username', 'password', 'name', 'email']
    
    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            username=username,
            password=password,
            email=validated_data['email']
        )

        customer = Customer.objects.create(user=user, **validated_data)
        return customer

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
        fields = ['id', 'customer', 'created_at', 'items']

class OrderItemSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    order_date = serializers.DateTimeField(source='order.created_at', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    customer_name = serializers.CharField(source='order.user.get_full_name', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'order_id', 'order_date', 'product_name', 'product_sku', 'quantity', 'price', 'customer_name', 'order_status', 'discounted_price']
        read_only_fields = ['id', 'order_id', 'order_date', 'product_name', 'product_sku', 'customer_name', 'order_status', 'discounted_price']

    def get_discounted_price(self, obj):
        promo_code = self.context.get('promo_code')
        if not promo_code:
            return None
        now = timezone.now()
        promotion = Promotion.objects.filter(
            promo_code=promo_code,
            applicable_products=obj.product,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()
        if promotion:
            price = float(obj.price)
            if promotion.discount_type == 'percentage':
                return price * (1 - float(promotion.discount_value) / 100)
            elif promotion.discount_type == 'fixed':
                return max(0, price - float(promotion.discount_value))
        return None

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    promo_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    total = serializers.SerializerMethodField()
    discounted_total = serializers.SerializerMethodField()
    address = serializers.CharField()
    city = serializers.CharField()
    postal_code = serializers.CharField()
    country = serializers.CharField()

    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'address', 'city', 'postal_code', 'country', 'total_amount', 'status', 'items', 'promo_code', 'total', 'discounted_total']
        read_only_fields = ['id', 'user', 'created_at', 'status', 'items', 'total', 'discounted_total']

    def get_total(self, obj):
        return sum(item.price * item.quantity for item in obj.items.all())

    def get_discounted_total(self, obj):
        promo_code = self.context.get('promo_code')
        if not promo_code:
            return self.get_total(obj)
        total = 0
        now = timezone.now()
        for item in obj.items.all():
            promotion = Promotion.objects.filter(
                promo_code=promo_code,
                applicable_products=item.product,
                is_active=True,
                start_date__lte=now,
                end_date__gte=now
            ).first()
            if promotion:
                price = float(item.price)
                discounted_price = (price * (1 - float(promotion.discount_value) / 100) if promotion.discount_type == 'percentage'
                                   else max(0, price - float(promotion.discount_value)))
                total += discounted_price * item.quantity
            else:
                total += item.price * item.quantity
        return total

    def validate_promo_code(self, value):
        if not value:
            return value
        now = timezone.now()
        promotion = Promotion.objects.filter(
            promo_code=value,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()
        if not promotion:
            raise serializers.ValidationError("Invalid or inactive promo code.")
        # Check if promo_code applies to any cart items
        cart_items = self.context.get('cart_items', [])
        applicable = False
        for item in cart_items:
            if promotion.applicable_products.filter(id=item['product']).exists():
                applicable = True
                break
        if not applicable:
            raise serializers.ValidationError("Promo code does not apply to any items in the cart.")
        return value

class PromotionSerializer(serializers.ModelSerializer):
    applicable_products = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = Promotion
        fields = [
            'id', 'title', 'description', 'start_date', 'end_date', 'promo_code',
            'discount_type', 'discount_value', 'applicable_products', 'banner_image',
            'is_active', 'created_at', 'updated_at', 'vendor'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'vendor']

    def get_banner_image(self, obj):
        if obj.banner_image:
            return self.context['request'].build_absolute_uri(obj.banner_image.url) if self.context.get('request') else f"{settings.MEDIA_URL}{obj.image}".lstrip('/')
        return None

    def validate(self, data):
        # Ensure discount_value is valid for discount_type
        if data.get('discount_type') == 'percentage' and data.get('discount_value') > 100:
            raise serializers.ValidationError("Percentage discount cannot exceed 100.")
        # Validate applicable_products belong to the vendor
        vendor = Vendor.objects.get(user=self.context['request'].user)
        products = data.get('applicable_products', [])
        for product in products:
            if product.vendor != vendor:
                raise serializers.ValidationError(f"Product {product.name} does not belong to this vendor.")
        return data

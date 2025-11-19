from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from vendors.models import Vendor

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer')
    name = models.CharField(max_length=100, blank=True)
    mobile_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name or 'User'} - {self.mobile_number}"

class OTP(models.Model):
    mobile_number = models.CharField(max_length=15, db_index=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mobile_number', '-created_at']),
        ]

    def is_valid(self):
        """Check if OTP is still valid (5 minutes)"""
        return self.created_at >= timezone.now() - timedelta(minutes=5)

    def __str__(self):
        return f"{self.mobile_number} - {self.otp}"

class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    sku = models.CharField(max_length=50, unique=True)
    stock = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return self.name

    @property
    def status(self):
        if self.stock == 0:
            return "Out of Stock"
        elif self.stock <= 5:  # threshold for low stock
            return "Low Stock"
        return "In Stock"

class Cart(models.Model):
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='cart')
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.customer:
            return f"Cart for {self.customer.name}"
        return f"Cart for session {self.session_key}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in cart"

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('ASSIGNED', 'Assigned'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    promo_code = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Order {self.id} by {self.user.name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} (x{self.quantity}) in Order {self.order.id}"

class Promotion(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    promo_code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    applicable_products = models.ManyToManyField(Product, related_name='promotions')
    banner_image = models.ImageField(upload_to='promotions/', blank=True, null=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='end_date_after_start_date'
            )
        ]

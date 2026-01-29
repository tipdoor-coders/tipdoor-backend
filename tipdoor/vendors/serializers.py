from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from .models import Vendor

class VendorSerializer(serializers.ModelSerializer):
    # Add User fields to the serializer
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    class Meta:
        model = Vendor
        fields = ['id', 'username', 'password', 'name', 'email', 'phone_number', 'address', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']

    def create(self, validated_data):
        # Extract User-related fields
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        email = validated_data.get('email')

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({'username': 'Username already exists'})
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'Email already exists'})

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            vendor = Vendor.objects.create(user=user, **validated_data)

        return vendor

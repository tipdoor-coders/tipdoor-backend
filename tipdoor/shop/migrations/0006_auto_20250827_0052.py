from django.db import migrations
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

def assign_vendor_and_sku(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    Vendor = apps.get_model('vendors', 'Vendor')
    User = apps.get_model('auth', 'User')

    # Create a default user if it doesn't exist
    default_user, created = User.objects.get_or_create(
        username='default_vendor',
        defaults={
            'email': 'default@vendor.com',
            'password': make_password(None)
        }
    )

    # Create a default vendor if it doesn't exist
    default_vendor, created = Vendor.objects.get_or_create(
        user=default_user,
        defaults={
            'name': 'System Vendor',
            'email': 'default@vendor.com',
            'phone_number': '',
            'address': '',
            'is_active': True,
        }
    )

    # Assign vendor and generate unique SKU for existing products
    for product in Product.objects.all():
        product.vendor = default_vendor
        product.sku = f'SKU-{product.id}-{product.name[:40]}'.replace(' ', '-')[:50]
        product.save()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_product_is_published_product_sku_product_stock_and_more'),
        ('vendors', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(assign_vendor_and_sku, reverse_code=migrations.RunPython.noop),
    ]

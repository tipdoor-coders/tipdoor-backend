from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('customer/products/', views.CustomerProductListView.as_view(), name='customer-product-list'),
    path('vendor/products/', views.VendorProductListCreateView.as_view(), name='vendor-product-list-create'),
    path('latest-arrivals/', views.LatestArrivalView.as_view(), name='latest-arrival'),
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.AddToCartView.as_view(), name='add-to-cart'),
    path('cart/update/<int:item_id>/', views.UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/remove/<int:item_id>/', views.RemoveCartItemView.as_view(), name='remove-cart-item'),
    path('user/', views.UserDetailView.as_view(), name='user-detail'),
    path('products/search', views.ProductSearchView.as_view(), name='product-search'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('products/<int:pk>', views.ProductDetailView.as_view(), name='product-detail'),
    path('vendor/products/<int:pk>/publish/', views.ProductPublishView.as_view(), name='product-publish'),
    path('vendor/products/<int:pk>/unpublish/', views.ProductUnpublishView.as_view(), name='product-unpublish'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/', views.OrderListView.as_view(), name='order-list'),
]

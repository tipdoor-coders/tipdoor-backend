from django.urls import path

from .views import ProductListCreateView, LatestArrivalView, ProductSearchView, RegisterView, ProductDetailView, OrderListView
from .views import CartView, AddToCartView, UpdateCartItemView, RemoveCartItemView, UserDetailView, OrderCreateView
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('latest-arrivals/', LatestArrivalView.as_view(), name='latest-arrival'),
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/update/<int:item_id>/', UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/remove/<int:item_id>/', RemoveCartItemView.as_view(), name='remove-cart-item'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('products/search', ProductSearchView.as_view(), name='product-search'),
    path('register/', RegisterView.as_view(), name='register'),
    path('products/<int:pk>', ProductDetailView.as_view(), name='product-detail'),
    path('orders/create/', OrderCreateView.as_view(), name='order-create'),
    path('orders/', OrderListView.as_view(), name='order-list'),
]

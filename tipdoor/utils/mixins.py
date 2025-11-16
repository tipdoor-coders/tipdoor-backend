from shop.models import Cart

class CartMixin:
    def get_cart(self, request):
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(customer=request.user.customer)
            return cart

        if not request.session.session_key:
            request.session.create()
        
        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
        return cart

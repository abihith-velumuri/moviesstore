# from django.shortcuts import render
# from django.shortcuts import get_object_or_404, redirect
# from movies.models import Movie
# from .utils import calculate_cart_total
# from .models import Order, Item
# from django.contrib.auth.decorators import login_required

# def index(request):
#     cart_total = 0
#     movies_in_cart = []
#     cart = request.session.get('cart', {})
#     movie_ids = list(cart.keys())
#     if (movie_ids != []):
#         movies_in_cart = Movie.objects.filter(id__in=movie_ids)
#         cart_total = calculate_cart_total(cart,
#             movies_in_cart)
#     template_data = {}
#     template_data['title'] = 'Cart'
#     template_data['movies_in_cart'] = movies_in_cart
#     template_data['cart_total'] = cart_total
#     return render(request, 'cart/index.html',
#         {'template_data': template_data})

# def add(request, id):
# # def add_to_cart(request, id):
#     get_object_or_404(Movie, id=id)
#     cart = request.session.get('cart', {})
#     cart[id] = request.POST['quantity']
#     request.session['cart'] = cart
#     # return redirect('home.index')
#     return redirect('cart.index')

# def clear(request):
#     request.session['cart'] = {}
#     return redirect('cart.index')

# @login_required
# def purchase(request):
#     cart = request.session.get('cart', {})
#     movie_ids = list(cart.keys())
#     if (movie_ids == []):
#         return redirect('cart.index')
#     movies_in_cart = Movie.objects.filter(id__in=movie_ids)
#     cart_total = calculate_cart_total(cart, movies_in_cart)
#     order = Order()
#     order.user = request.user
#     order.total = cart_total
#     order.save()
#     for movie in movies_in_cart:
#         item = Item()
#         item.movie = movie
#         item.price = movie.price
#         item.order = order
#         item.quantity = cart[str(movie.id)]
#         item.save()
#     request.session['cart'] = {}
#     template_data = {}
#     template_data['title'] = 'Purchase confirmation'
#     template_data['order_id'] = order.id
#     return render(request, 'cart/purchase.html',
#         {'template_data': template_data})

from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from movies.models import Movie
from .utils import calculate_cart_total
from .models import Order, Item
from django.contrib.auth.decorators import login_required
from django.db import transaction  # <-- NEW

def index(request):
    cart_total = 0
    movies_in_cart = []
    cart = request.session.get('cart', {})
    movie_ids = list(cart.keys())
    if (movie_ids != []):
        movies_in_cart = Movie.objects.filter(id__in=movie_ids)
        cart_total = calculate_cart_total(cart,
            movies_in_cart)
    template_data = {}
    template_data['title'] = 'Cart'
    template_data['movies_in_cart'] = movies_in_cart
    template_data['cart_total'] = cart_total
    return render(request, 'cart/index.html',
        {'template_data': template_data})

def add(request, id):
    """
    Add a movie to the cart, respecting inventory:
    - If amount_left is None => unlimited
    - If amount_left == 0 => do nothing (sold out)
    - If amount_left > 0 => clamp quantity to available
    """
    movie = get_object_or_404(Movie, id=id)

    # Parse requested quantity (default 1)
    try:
        requested_qty = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        requested_qty = 1
    if requested_qty < 1:
        requested_qty = 1

    # Respect inventory
    if movie.amount_left is not None:
        if movie.amount_left <= 0:
            # sold out: don't add
            return redirect('cart.index')
        # clamp to available
        requested_qty = min(requested_qty, movie.amount_left)

    cart = request.session.get('cart', {})

    # Keep your existing overwrite behavior (simplest):
    cart[str(id)] = str(requested_qty)

    request.session['cart'] = cart
    return redirect('cart.index')

def clear(request):
    request.session['cart'] = {}
    return redirect('cart.index')

@login_required
def purchase(request):
    """
    Create an order for items in the cart, safely decrementing stock:
    - Lock rows with select_for_update() to avoid race conditions.
    - For limited inventory, clamp purchase quantity to what's left.
    - Skip items that are fully sold out by the time of purchase.
    """
    cart = request.session.get('cart', {})
    movie_ids = list(cart.keys())
    if (movie_ids == []):
        return redirect('cart.index')

    movies_in_cart = Movie.objects.filter(id__in=movie_ids)
    cart_total = calculate_cart_total(cart, movies_in_cart)

    # If everything was filtered out or total is zero, still proceed to keep UX simple
    order = Order()
    order.user = request.user
    order.total = cart_total
    order.save()

    # Use a transaction so stock updates are atomic
    with transaction.atomic():
        # Re-fetch and lock each movie row during update
        for movie in movies_in_cart:
            # Determine requested quantity from cart (stored as string)
            try:
                requested_qty = int(cart.get(str(movie.id), 0))
            except (TypeError, ValueError):
                requested_qty = 0

            if requested_qty <= 0:
                continue

            locked_movie = Movie.objects.select_for_update().get(pk=movie.id)

            # Unlimited inventory
            if locked_movie.amount_left is None:
                qty_to_buy = requested_qty
            else:
                # Limited inventory: clamp to available
                if locked_movie.amount_left <= 0:
                    qty_to_buy = 0
                else:
                    qty_to_buy = min(requested_qty, locked_movie.amount_left)

            if qty_to_buy <= 0:
                # Nothing left for this movie; skip creating an Item
                continue

            # Create the order item with the (possibly clamped) quantity
            item = Item()
            item.movie = locked_movie
            item.price = locked_movie.price
            item.order = order
            item.quantity = qty_to_buy
            item.save()

            # Decrement stock if limited
            if locked_movie.amount_left is not None:
                locked_movie.amount_left = max(0, locked_movie.amount_left - qty_to_buy)
                locked_movie.save(update_fields=['amount_left'])

    # Clear cart after purchase
    request.session['cart'] = {}

    template_data = {}
    template_data['title'] = 'Purchase confirmation'
    template_data['order_id'] = order.id
    return render(request, 'cart/purchase.html',
        {'template_data': template_data})

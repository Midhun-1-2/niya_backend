from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Announcement,
    Category,
    HeroSlide,
    Order,
    OrderItem,
    Policy,
    Product,
    ProductImage,
    PromoBanner,
    Section,
    Wishlist,
)
from .permissions import IsAdminOrReadOnly
from .serializers import (
    AnnouncementSerializer,
    CategorySerializer,
    CheckoutSerializer,
    HeroSlideSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    PolicySerializer,
    ProductSerializer,
    PromoBannerSerializer,
    SectionSerializer,
    WishlistSerializer,
)

FREE_SHIPPING_THRESHOLD = Decimal('1999')
SHIPPING_FEE = Decimal('149')

MAX_HERO_SLIDES = 4
MAX_IMAGES_PER_COLOR = 4
MAX_SECTIONS = 10


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.products.exists():
            return Response(
                {'detail': 'This category has products linked to it and cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def create(self, request, *args, **kwargs):
        if Section.objects.count() >= MAX_SECTIONS:
            return Response(
                {'detail': f'Maximum of {MAX_SECTIONS} sections allowed — delete one before adding another.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.slug == 'sale':
            return Response(
                {'detail': 'The Sale section is built-in and cannot be deleted — turn it off instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.products.exists():
            return Response(
                {'detail': 'This section has products linked to it and cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAdminOrReadOnly]


class HeroSlideViewSet(viewsets.ModelViewSet):
    queryset = HeroSlide.objects.all()
    serializer_class = HeroSlideSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        if HeroSlide.objects.count() >= MAX_HERO_SLIDES:
            return Response(
                {'detail': f'Maximum of {MAX_HERO_SLIDES} hero slides allowed — delete one before adding another.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)


class PromoBannerViewSet(viewsets.ModelViewSet):
    queryset = PromoBanner.objects.all()
    serializer_class = PromoBannerSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        product = serializer.save(created_by=self.request.user)
        self._save_color_images(product)

    def perform_update(self, serializer):
        product = serializer.save()
        colors = [c.strip() for c in (product.colors or '').split(',') if c.strip()]
        product.images.exclude(color__in=colors or ['']).delete()
        remove_ids = self._removed_image_ids()
        if remove_ids:
            product.images.filter(id__in=remove_ids).delete()
        self._save_color_images(product)

    def _removed_image_ids(self):
        data = self.request.data
        return data.getlist('remove_image_ids') if hasattr(data, 'getlist') else data.get('remove_image_ids', [])

    def _save_color_images(self, product):
        colors = [c.strip() for c in (product.colors or '').split(',') if c.strip()]
        for color in colors or ['']:
            files = self.request.FILES.getlist(f'images_{color}')
            if not files:
                continue
            existing_count = product.images.filter(color=color).count()
            room = max(0, MAX_IMAGES_PER_COLOR - existing_count)
            for i, f in enumerate(files[:room]):
                ProductImage.objects.create(product=product, color=color, image=f, order=existing_count + i)


class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'type'
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        existing = set(Policy.objects.values_list('type', flat=True))
        missing = [t for t, _ in Policy.TYPE_CHOICES if t not in existing]
        if missing:
            Policy.objects.bulk_create([Policy(type=t) for t in missing])
        return Policy.objects.all()


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']
    # The frontend only ever knows a product's id, never a wishlist row's own
    # id — so look items up by product rather than by the Wishlist pk. The
    # router still generates /api/wishlist/<pk>/, it's just that "pk" here
    # means "product id".
    lookup_field = 'product_id'
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product', 'product__category')

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product_id') or request.data.get('product')
        if not product_id:
            return Response({'product_id': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        product = get_object_or_404(Product, pk=product_id)
        # get_or_create keeps repeated "add" clicks (e.g. a double-fired
        # toggle) idempotent instead of raising a unique_together conflict.
        wishlist_item, _ = Wishlist.objects.get_or_create(user=request.user, product=product)
        serializer = self.get_serializer(wishlist_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Order.objects.select_related('user').prefetch_related('items__product__category')
        user = self.request.user
        if user.is_staff:
            user_id = self.request.query_params.get('user')
            return qs.filter(user_id=user_id) if user_id else qs
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        checkout = CheckoutSerializer(data=request.data)
        checkout.is_valid(raise_exception=True)

        user = request.user
        data = checkout.validated_data
        ship_name = data.get('ship_name') or user.name
        ship_phone = data.get('ship_phone') or user.phone_number
        ship_house_number = data.get('ship_house_number') or user.house_number
        ship_address = data.get('ship_address') or user.address
        ship_city = data.get('ship_city') or user.city
        ship_state = data.get('ship_state') or user.state
        ship_country = data.get('ship_country') or user.country
        ship_pincode = data.get('ship_pincode') or user.pincode

        if not ship_house_number or not ship_address:
            return Response(
                {'detail': 'Please provide a complete shipping address before placing an order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        line_items = []
        subtotal = Decimal('0')
        for entry in checkout.validated_data['items']:
            product = get_object_or_404(Product, pk=entry['product_id'])
            qty = entry['quantity']
            if product.quantity < qty:
                return Response(
                    {'detail': f'Only {product.quantity} left in stock for "{product.name}".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subtotal += product.price * qty
            line_items.append((product, qty, entry.get('color', '')))

        shipping_fee = Decimal('0') if subtotal == 0 or subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE

        order = Order.objects.create(
            user=user,
            payment_method=data.get('payment_method', 'cod'),
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=subtotal + shipping_fee,
            ship_name=ship_name,
            ship_phone=ship_phone,
            ship_house_number=ship_house_number,
            ship_address=ship_address,
            ship_city=ship_city,
            ship_state=ship_state,
            ship_country=ship_country,
            ship_pincode=ship_pincode,
        )
        for product, qty, color in line_items:
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, color=color,
                price=product.price, quantity=qty,
            )
            product.quantity -= qty
            product.save(update_fields=['quantity'])

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        if request.user.is_staff:
            serializer = OrderStatusSerializer(order, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            if order.user_id != request.user.id:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            if request.data.get('status') != 'cancelled':
                return Response({'detail': 'You can only cancel your order.'}, status=status.HTTP_403_FORBIDDEN)
            if order.status not in Order.CUSTOMER_CANCELLABLE_STATUSES:
                return Response(
                    {'detail': 'This order has already shipped and can no longer be cancelled.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = 'cancelled'
            order.save(update_fields=['status'])

        timestamp_field = f'{order.status}_at'
        if hasattr(order, timestamp_field) and getattr(order, timestamp_field) is None:
            setattr(order, timestamp_field, timezone.now())
            order.save(update_fields=[timestamp_field])

        return Response(self.get_serializer(order).data)

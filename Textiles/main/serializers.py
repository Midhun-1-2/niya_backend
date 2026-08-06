from django.utils import timezone
from rest_framework import serializers

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


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='products.count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'is_active', 'order', 'product_count']
        read_only_fields = ['id', 'slug']


class SectionSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='products.count', read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'name', 'slug', 'is_active', 'show_in_home', 'order', 'product_count']
        read_only_fields = ['id', 'slug']


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'text', 'icon', 'is_active', 'is_highlight', 'order', 'date_from', 'date_to']
        read_only_fields = ['id']

    def validate(self, attrs):
        is_highlight = attrs.get('is_highlight', getattr(self.instance, 'is_highlight', False))
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', True))
        date_from = attrs.get('date_from', getattr(self.instance, 'date_from', None))
        date_to = attrs.get('date_to', getattr(self.instance, 'date_to', None))

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({'date_to': 'End date cannot be before the start date.'})

        if (
            self.instance
            and self.instance.is_highlight
            and self.instance.is_active
            and self.instance.date_from
            and self.instance.date_to
            and self.instance.date_from <= timezone.now().date() <= self.instance.date_to
        ):
            # Deactivating is always allowed — it's the sanctioned way to end a live
            # highlight early (the "delete" action archives it into history instead
            # of hard-deleting), so it must bypass the lock.
            is_deactivating = attrs.get('is_active') is False
            if not is_deactivating:
                locked_fields = {'text', 'icon', 'date_from', 'date_to', 'is_active', 'is_highlight'}
                changed = {
                    f for f in locked_fields if f in attrs and attrs[f] != getattr(self.instance, f)
                }
                if changed:
                    raise serializers.ValidationError(
                        'This highlight is currently live and cannot be edited until it ends.'
                    )

        if is_highlight and is_active and date_from and date_to:
            clashing = Announcement.objects.filter(
                is_highlight=True, is_active=True, date_from__lte=date_to, date_to__gte=date_from,
            )
            if self.instance:
                clashing = clashing.exclude(pk=self.instance.pk)
            if clashing.exists():
                raise serializers.ValidationError(
                    {'date_from': 'Another highlight is already active in this date range.'}
                )

        return attrs


class HeroSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSlide
        fields = ['id', 'image', 'is_active', 'order']
        read_only_fields = ['id']


class PromoBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoBanner
        fields = [
            'id', 'image', 'eyebrow', 'title', 'subtitle', 'cta_label', 'cta_link', 'show_button', 'is_active',
            'order',
        ]
        read_only_fields = ['id']


class PolicySerializer(serializers.ModelSerializer):
    label = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Policy
        fields = ['type', 'label', 'content', 'updated_at']
        read_only_fields = ['type', 'label', 'updated_at']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'color', 'image', 'order']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field='slug', queryset=Category.objects.all())
    sections = serializers.SlugRelatedField(
        slug_field='slug', queryset=Section.objects.all(), many=True, required=False
    )
    discount_percent = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'sections', 'description', 'price', 'mrp', 'colors', 'quantity',
            'image', 'images', 'discount_percent', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_discount_percent(self, obj):
        if obj.mrp and obj.mrp > obj.price:
            return round((obj.mrp - obj.price) / obj.mrp * 100)
        return 0

    def validate(self, attrs):
        price = attrs.get('price', getattr(self.instance, 'price', None))
        mrp = attrs.get('mrp', getattr(self.instance, 'mrp', None))
        if price is not None and mrp is not None and price > mrp:
            raise serializers.ValidationError({'price': 'Selling price cannot be higher than MRP.'})
        return attrs


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source='product', queryset=Product.objects.all(), write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrderItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'product_name', 'category', 'image', 'color', 'price', 'quantity']
        read_only_fields = fields

    def get_image(self, obj):
        if not (obj.product and obj.product.image):
            return None
        request = self.context.get('request')
        url = obj.product.image.url
        return request.build_absolute_uri(url) if request else url

    def get_product_id(self, obj):
        return obj.product_id

    def get_category(self, obj):
        return obj.product.category.slug if obj.product else None


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_name', 'user_phone', 'user_email', 'status', 'payment_method', 'subtotal',
            'shipping_fee', 'total', 'ship_name', 'ship_phone', 'ship_house_number', 'ship_address', 'ship_city',
            'ship_state', 'ship_country', 'ship_pincode', 'created_at', 'confirmed_at', 'shipped_at',
            'delivered_at', 'cancelled_at', 'item_count', 'items',
        ]
        read_only_fields = fields

    def get_item_count(self, obj):
        return sum(item.quantity for item in obj.items.all())


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']

    def validate_status(self, value):
        if self.instance and self.instance.status in Order.LOCKED_STATUSES:
            raise serializers.ValidationError('This order has reached a final status and cannot be updated.')
        return value


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    color = serializers.CharField(required=False, allow_blank=True, max_length=20)


class CheckoutSerializer(serializers.Serializer):
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_CHOICES, required=False, default='cod')
    # Optional shipping override — omitted/blank fields fall back to the
    # user's saved profile address (see OrderViewSet.create).
    ship_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    ship_phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    ship_house_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ship_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ship_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ship_state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ship_country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ship_pincode = serializers.CharField(max_length=20, required=False, allow_blank=True)

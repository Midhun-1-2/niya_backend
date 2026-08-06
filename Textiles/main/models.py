import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Section(models.Model):
    """Homepage product section, e.g. Bestsellers, New Arrivals — admin-managed."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    show_in_home = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Announcement(models.Model):
    """A single scrolling message in the strip above the header."""

    text = models.CharField(max_length=200)
    icon = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)
    is_highlight = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    # Only meaningful when is_highlight=True — bounds the window the coupon-style
    # banner is shown in, and lets us block overlapping highlights server-side.
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text


class HeroSlide(models.Model):
    """A rotating photo in the homepage hero banner — admin-managed, capped at 4."""

    image = models.ImageField(upload_to='hero/')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'Hero slide #{self.pk}'


class PromoBanner(models.Model):
    """A promotional banner shown between homepage sections — admin-managed, capped at 5, auto-rotated."""

    image = models.ImageField(upload_to='promo/')
    eyebrow = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    cta_label = models.CharField(max_length=50, blank=True, default='Discover')
    cta_link = models.CharField(max_length=200, blank=True, default='/shop')
    show_button = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.title


class Product(models.Model):
    # UUID instead of a sequential int — product IDs are exposed directly in
    # public URLs (/product/bN, /api/products/N/), and sequential integers
    # make every product trivially enumerable by anyone hitting the API
    # directly (independent of whatever the category/section is_active
    # filtering does at the frontend level).
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    sections = models.ManyToManyField(Section, blank=True, related_name='products')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    colors = models.CharField(max_length=255, blank=True, help_text='Comma-separated hex codes')
    quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Up to 4 gallery images per color variant, shown when that color is selected."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    color = models.CharField(max_length=20, help_text='Hex code, must match one of the product colors')
    image = models.ImageField(upload_to='products/gallery/')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['color', 'order']

    def __str__(self):
        return f'{self.product.name} — {self.color} #{self.order}'


class Policy(models.Model):
    """Fixed set of admin-editable legal documents shown to customers."""

    TERMS = 'terms'
    RETURN = 'return'
    REFUND = 'refund'
    TYPE_CHOICES = [
        (TERMS, 'Terms & Conditions'),
        (RETURN, 'Return Policy'),
        (REFUND, 'Refund Policy'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, unique=True)
    content = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_type_display()


class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('upi', 'UPI'),
        ('card', 'Card'),
    ]
    # Terminal statuses — once an order reaches one of these, staff can no
    # longer change its status (enforced in OrderViewSet.partial_update).
    LOCKED_STATUSES = ('delivered', 'cancelled')
    # Customers may self-cancel only while the order hasn't shipped yet.
    CUSTOMER_CANCELLABLE_STATUSES = ('placed', 'confirmed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    # Shipping details are snapshotted at order time so a later profile edit
    # doesn't silently rewrite past order history.
    ship_name = models.CharField(max_length=150)
    ship_phone = models.CharField(max_length=10)
    ship_house_number = models.CharField(max_length=100)
    ship_address = models.CharField(max_length=255)
    ship_city = models.CharField(max_length=100)
    ship_state = models.CharField(max_length=100)
    ship_country = models.CharField(max_length=100)
    ship_pincode = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {str(self.id)[:8]} — {self.user}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    product_name = models.CharField(max_length=200)
    color = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.quantity} x {self.product_name}'


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'product')

    def __str__(self):
        return f'{self.user} → {self.product}'

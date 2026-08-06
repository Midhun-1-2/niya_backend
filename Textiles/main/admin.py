from django.contrib import admin

from .models import Announcement, Category, HeroSlide, Policy, Product, ProductImage, PromoBanner, Section, Wishlist


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'show_in_home', 'order')
    list_filter = ('is_active', 'show_in_home')
    search_fields = ('name',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('text', 'icon', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('text',)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'order', 'created_at')
    list_filter = ('is_active',)


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active')
    list_filter = ('is_active',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'mrp', 'quantity', 'created_by', 'created_at')
    list_filter = ('category', 'sections')
    search_fields = ('name', 'description')
    inlines = [ProductImageInline]


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('type', 'updated_at')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__phone_number', 'product__name')

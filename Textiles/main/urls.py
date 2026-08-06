from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementViewSet,
    CategoryViewSet,
    HeroSlideViewSet,
    OrderViewSet,
    PolicyViewSet,
    ProductViewSet,
    PromoBannerViewSet,
    SectionViewSet,
    WishlistViewSet,
)

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('categories', CategoryViewSet, basename='category')
router.register('sections', SectionViewSet, basename='section')
router.register('announcements', AnnouncementViewSet, basename='announcement')
router.register('hero-slides', HeroSlideViewSet, basename='heroslide')
router.register('promo-banners', PromoBannerViewSet, basename='promobanner')
router.register('policies', PolicyViewSet, basename='policy')
router.register('wishlist', WishlistViewSet, basename='wishlist')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('api/', include(router.urls)),
]

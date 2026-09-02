from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("stocks", views.StockViewSet, basename="stock")
router.register("transactions", views.TransactionViewSet, basename="transaction")
router.register("broker-plans", views.BrokerPlanViewSet, basename="brokerplan")
router.register("corporate-actions", views.CorporateActionViewSet, basename="corporateaction")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),

    path("portfolio/", views.PortfolioListView.as_view(), name="portfolio"),
    path("portfolio/summary/", views.PortfolioSummaryView.as_view(), name="portfolio-summary"),
    path("portfolio/<int:stock_id>/", views.StockDetailView.as_view(), name="stock-detail"),
    path("portfolio/analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("portfolio/rebuild/", views.rebuild_view, name="rebuild"),

    path("prices/<int:stock_id>/", views.PriceView.as_view(), name="price"),

    path("", include(router.urls)),
]

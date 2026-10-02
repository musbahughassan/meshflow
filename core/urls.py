from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from djoser.views import UserViewSet
from rest_framework.routers import DefaultRouter




router = DefaultRouter()

router.register('register', UserViewSet, basename='signup')

urlpatterns = router.urls + [
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='login-refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='logout'),

]


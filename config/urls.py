from django.contrib import admin
<<<<<<< HEAD
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('restaurants.urls')),
=======
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # language switcher (set_language)
    path("staff/", include("staff.urls")),
    path("", include("customer.urls")),
>>>>>>> upstream/main
]

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # language switcher (set_language)
    path("staff/", include("staff.urls")),
    path("", include("customer.urls")),
]

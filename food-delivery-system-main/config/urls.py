from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("staff/", include("staff.urls")),
    path("core/", include("core.urls")),
    path("", include("customer.urls")),
]

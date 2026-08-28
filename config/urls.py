"""URL configuration for the product service."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]

# Django serves uploaded files only while DEBUG is on — this is a development
# convenience, not a production path. There a web server or object storage
# delivers them.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""URL configuration for the product service."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Versioned from the start: it costs nothing now and is the difference
# between a prototype and a service that can ship a breaking change.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/v1/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path('api/v1/', include('catalog.urls')),
]

# Django serves uploaded files only while DEBUG is on — this is a development
# convenience, not a production path. There a web server or object storage
# delivers them.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('website.urls')),
    # for the Django REST framework browsable API and development 
    path('api-auth/', include('rest_framework.urls')),
]

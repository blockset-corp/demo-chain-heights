"""server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from app import views
import debug_toolbar

urlpatterns = [
    path('', views.index, name='index'),
    path('service/<slug:service_slug>/', views.service_detail, name='service_detail'),
    path('error/<int:error_id>/', views.error_detail, name='error_detail'),
    path('difftable/', views.difftable_partial, name='difftable'),
    path('validtable/', views.validtable_partial, name='validtable'),
    path('json_summary/', views.json_summary, name='json_summary'),
    path('admin/', admin.site.urls),
    path('__debug__/', include(debug_toolbar.urls)),
]

from django.contrib import admin
from .models import Service, CheckResult


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    fields = ('name', 'supported_chains')


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    pass

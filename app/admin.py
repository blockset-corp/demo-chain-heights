from django.contrib import admin
from .models import Service, Blockchain, CheckInstance, ChainHeightResult


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


@admin.register(Blockchain)
class BlockchainAdmin(admin.ModelAdmin):
    list_display = ('service', 'name', 'slug', 'is_testnet')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('service')


@admin.register(CheckInstance)
class CheckInstanceAdmin(admin.ModelAdmin):
    pass


@admin.register(ChainHeightResult)
class ChainHeightResultAdmin(admin.ModelAdmin):
    list_display = ('service_slug', 'blockchain_slug', 'check_instance_id', 'status', 'duration_ms', 'height')
    ordering = ('-check_instance_id', 'blockchain__slug', 'blockchain__service__slug')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('blockchain', 'blockchain__service')

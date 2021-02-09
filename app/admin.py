from django.contrib import admin
from .models import Service, Blockchain, ChainHeightResult


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


@admin.register(Blockchain)
class BlockchainAdmin(admin.ModelAdmin):
    list_display = ('service', 'name', 'slug', 'is_testnet')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('service')


@admin.register(ChainHeightResult)
class ChainHeightResultAdmin(admin.ModelAdmin):
    list_display = ('service_slug', 'blockchain_slug', 'status', 'height')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('blockchain', 'blockchain__service')

from django.contrib import admin
from .models import Service, Blockchain, BlockchainMeta, CheckInstance, \
    ChainHeightResult, CheckError


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


@admin.register(BlockchainMeta)
class BlockchainMeta(admin.ModelAdmin):
    list_display = ('display_name', 'chain_slug')


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
    list_display = ('service_slug', 'blockchain_slug', 'check_instance_id', 'status',
                    'duration_ms', 'height', 'difference_from_best', 'best_service')
    ordering = ('-check_instance_id', 'blockchain__slug', 'blockchain__service__slug')
    readonly_fields = ('blockchain', 'check_instance', 'best_result')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta', 'best_result__blockchain',
            'best_result__blockchain__service'
        )


@admin.register(CheckError)
class CheckErrorAdmin(admin.ModelAdmin):
    pass

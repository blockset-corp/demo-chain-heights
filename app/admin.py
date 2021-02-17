from django.contrib import admin
from .models import Service, Blockchain, BlockchainMeta, CheckInstance, \
    ChainHeightResult, CheckError, PingResult


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
    list_display = ('run_id', 'type', 'started', 'duration')

    def duration(self, obj):
        if obj.completed is not None:
            ms = int((obj.completed - obj.started).total_seconds() * 1000)
            return f'{ms} ms'
        else:
            return 'incomplete'

    def run_id(self, obj):
        return obj.pk
    run_id.short_description = 'Run #'


@admin.register(ChainHeightResult)
class ChainHeightResultAdmin(admin.ModelAdmin):
    list_display = ('service_slug', 'blockchain_slug', 'run_number', 'status',
                    'duration_ms', 'height', 'difference_from_best', 'best_service')
    ordering = ('-check_instance_id', 'blockchain__slug', 'blockchain__service__slug')
    readonly_fields = ('blockchain', 'check_instance', 'best_result', 'error_details')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta', 'best_result__blockchain',
            'best_result__blockchain__service'
        )

    def run_number(self, obj):
        return obj.check_instance_id
    run_number.short_description = 'Run #'


@admin.register(PingResult)
class PingResultAdmin(admin.ModelAdmin):
    list_display = ('service', 'status', 'duration_ms')
    ordering = ('-pk',)
    readonly_fields = ('service', 'check_instance', 'error_details')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('service')

    def service_slug(self, obj):
        return obj.service.slug
    service_slug.short_description = 'Service'

    def duration_ms(self, obj):
        return f'{obj.duration} ms'
    duration_ms.short_description = 'Duration MS'


@admin.register(CheckError)
class CheckErrorAdmin(admin.ModelAdmin):
    list_display = ('created', 'blockchain_slug', 'service_slug', 'error_message_truncated')
    ordering = ('-pk',)
    readonly_fields = ('check_instance', 'blockchain')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('blockchain', 'blockchain__service', 'check_instance')

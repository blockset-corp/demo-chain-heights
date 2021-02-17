import re
import datetime
from collections import defaultdict
from django.db import models
from django.db.models import Q, F, Avg, Count, Max, Min
from django.db.models.functions import Trunc
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from autoslug import AutoSlugField

CHECK_TYPE_BLOCK_HEIGHT = 'bh'
CHECK_TYPE_PING = 'p'
CHECK_TYPES = (
    (CHECK_TYPE_BLOCK_HEIGHT, 'Block Height'),
    (CHECK_TYPE_PING, 'Ping'),
)

RESULT_STATUS_OK = 'ok'
RESULT_STATUS_ERR = 'er'
RESULT_STATUS_WARN = 'wr'

RESULT_STATUSES = (
    (RESULT_STATUS_OK, 'Ok'),
    (RESULT_STATUS_ERR, 'Error'),
    (RESULT_STATUS_WARN, 'Warn')
)


class Service(models.Model):
    name = models.CharField(max_length=60)
    slug = AutoSlugField(populate_from='name')
    bulk_chain_query = models.BooleanField(default=False,
                                           help_text='Whether or not to fetch chain height updates in bulk')
    private = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class BlockchainMeta(models.Model):
    display_name = models.CharField(max_length=60, help_text='Well-known proper noun for this blockchain')
    chain_slug = models.SlugField(help_text='Common slug for this blockchain not including network prefix')
    mainnet_slug = models.CharField(max_length=50, default='mainnet')
    testnet_slugs = ArrayField(models.CharField(max_length=25, blank=True),
                               help_text='Testnet slug (or slugs) such as "testnet" or "ropsten"')
    height_tolerance_success = models.IntegerField(default=0,
                                                   help_text='Number of blocks behind that is considered OK')
    height_tolerance_warning = models.IntegerField(default=-1,
                                                   help_text='Number of blocks behind that should emit a warning')
    height_tolerance_error = models.IntegerField(default=-2,
                                                 help_text='Number of blocks behind that should sound the alarms')

    def __str__(self):
        return self.display_name


class Blockchain(models.Model):
    name = models.CharField(max_length=60)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    slug = models.CharField(max_length=60)
    is_testnet = models.BooleanField(default=False)
    meta = models.ForeignKey(BlockchainMeta, on_delete=models.SET_NULL, null=True)
    ignore = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=('service', 'slug'), name='service_blockchain_slug')
        ]

    def __str__(self):
        return f'{self.service} {self.name}'

    def create_meta_if_not_exists(self):
        slug, network_slug = self.slug.split('-')
        metas = BlockchainMeta.objects.filter(chain_slug=slug)
        if metas.count() > 0:
            self.meta = metas.first()
            self.save()
        else:
            if network_slug not in ('mainnet', 'testnet'):
                testnet_slug = network_slug
            else:
                testnet_slug = 'testnet'
            meta = BlockchainMeta.objects.create(
                display_name=' '.join(self.name.split()[0:-1]),
                chain_slug=slug,
                testnet_slugs=[testnet_slug]
            )
            self.meta = meta
            self.save()


class CheckInstance(models.Model):
    type = models.CharField(choices=CHECK_TYPES, max_length=2, db_column='check_type')
    started = models.DateTimeField()
    completed = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=('type', '-completed'), name='check_type_completed')
        ]

    def __str__(self):
        s = f'{self.type} {self.started}'
        if self.completed:
            dur = self.completed - self.started
            s = s + f' {dur}'
        return s


class ChainHeightResultQuerySet(models.QuerySet):
    def for_service(self, service, check_instance=None):
        kw = {'blockchain__service': service}
        if check_instance is not None:
            kw['check_instance'] = check_instance
        exclude = (
                Q(check_instance__completed__isnull=True)
                | Q(blockchain__meta__isnull=True)
                | Q(blockchain__ignore=True)
        )
        return self.filter(**kw).exclude(exclude)

    def no_errors(self):
        return self.exclude(~Q(error_details__isnull=True) | ~Q(error=''))

    def common_related(self):
        return self.select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta',
            'best_result__blockchain', 'best_result__blockchain__service'
        )

    def get_hourly_stats(self, distance=datetime.timedelta(days=7)):
        now = timezone.now()
        then = now - distance
        averages = self.filter(
            check_instance__started__gt=then
        ).exclude(
            check_instance__completed__isnull=True
        ).annotate(
            started_hour=Trunc('started', 'hour'),
            diff=F('height') - F('best_result__height')
        ).values(
            'blockchain__slug', 'started_hour'
        ).annotate(
            diff_avg=Avg('diff', filter=Q(error_details__isnull=True) & Q(error='')),
            error_count=Count('id', filter=Q(error_details__isnull=False) | ~Q(error='')),
            success_count=Count('id', filter=Q(error_details__isnull=True) & Q(error=''))
        )
        tick_time_format = '%y-%m-%d %H:00'
        during_buckets = defaultdict(dict)
        for agg in averages:
            time_bucket = agg['started_hour'].strftime(tick_time_format)
            during_buckets[agg['blockchain__slug']][time_bucket] = {
                'diff_avg': agg['diff_avg'],
                'error_count': agg['error_count'],
                'success_count': agg['success_count']
            }
        hours = int(distance.total_seconds() / 60 / 60)
        chains = defaultdict(lambda: {'labels': [], 'data': []})
        known_chains = list(during_buckets.keys())
        known_chains.sort()
        empty_value = {'diff_avg': 0.0, 'error_count': 0, 'success_count': 0}
        for i in range(hours, -1, -1):
            date = (now - datetime.timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            tick_date = date.strftime(tick_time_format)
            for chain_id in known_chains:
                value = dict(empty_value)
                value.update(during_buckets[chain_id].get(tick_date, empty_value))
                chains[chain_id]['labels'].append(tick_date)
                chains[chain_id]['data'].append(value)
        return chains


class ChainHeightResult(models.Model):
    blockchain = models.ForeignKey(Blockchain, on_delete=models.CASCADE)
    check_instance = models.ForeignKey(CheckInstance, on_delete=models.CASCADE, related_name='results')
    started = models.DateTimeField()
    duration = models.IntegerField(help_text='Duration in milliseconds')
    status = models.CharField(max_length=2, choices=RESULT_STATUSES)
    height = models.IntegerField(default=0)
    error = models.TextField(default='')
    error_details = models.ForeignKey('CheckError', null=True, on_delete=models.SET_NULL)
    best_result = models.ForeignKey('ChainHeightResult', on_delete=models.CASCADE, null=True)

    objects = ChainHeightResultQuerySet.as_manager()

    def __str__(self):
        return f'{self.blockchain} {self.get_status_display()} {self.height}'

    def service_slug(self):
        return self.blockchain.service.slug

    service_slug.short_description = 'Service'

    def blockchain_slug(self):
        return self.blockchain.slug

    blockchain_slug.short_description = 'Blockchain'

    def duration_ms(self):
        return f'{self.duration}ms'

    def best_service(self):
        if self.best_result is None:
            return 'unknown'
        return self.best_result.blockchain.service.slug

    def difference_from_best(self):
        if self.best_result is None:
            return 0
        return self.height - self.best_result.height

    difference_from_best.short_description = 'Diff'

    def difference_from_best_status(self):
        diff = self.difference_from_best()
        if diff <= -abs(self.blockchain.meta.height_tolerance_error) or diff > 0:
            return 'danger'
        if diff <= -abs(self.blockchain.meta.height_tolerance_warning):
            return 'warning'
        if diff >= -abs(self.blockchain.meta.height_tolerance_success):
            return 'success'


class PingResultQuerySet(models.QuerySet):
    def get_minutely_stats(self, distance=datetime.timedelta(days=7)):
        now = timezone.now()
        then = now - distance
        results = self.filter(
            check_instance__started__gt=then,
            check_instance__completed__isnull=False
        ).annotate(
            started_minute=Trunc('started', 'minute'),
        ).values(
            'started_minute'
        ).annotate(
            min_dur=Min('duration'),
            max_dur=Max('duration'),
            avg_dur=Avg('duration'),
            error_count=Count('id', filter=Q(error_details__isnull=False))
        )
        tick_time_format = '%y-%m-%d %H:%M'
        tick_buckets = {}
        for result in results:
            result['avg_dur'] = int(result['avg_dur'])
            time_bucket = result['started_minute'].strftime(tick_time_format)
            tick_buckets[time_bucket] = result
        all_ticks = []
        minutes = int(distance.total_seconds() / 60)
        for i in range(minutes, -1, -1):
            date = (now - datetime.timedelta(minutes=i)).replace(second=0, microsecond=0)
            tick_date = date.strftime(tick_time_format)
            tick = [0, 0, 0, 0, int(date.timestamp())]
            tick_result = tick_buckets.get(tick_date, None)
            if tick_result is not None:
                tick[0] = tick_result['min_dur']
                tick[1] = tick_result['max_dur']
                tick[2] = tick_result['avg_dur']
                tick[3] = tick_result['error_count']
            all_ticks.append(tick)
        print(len(all_ticks))
        return all_ticks


class PingResult(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    check_instance = models.ForeignKey(CheckInstance, on_delete=models.CASCADE, related_name='pings')
    started = models.DateTimeField()
    duration = models.IntegerField()
    status = models.CharField(max_length=2, choices=RESULT_STATUSES)
    error_details = models.ForeignKey('CheckError', null=True, on_delete=models.SET_NULL)

    objects = PingResultQuerySet.as_manager()

    def __str__(self):
        return f'{self.service.slug} {self.get_status_display()}'


ERROR_TAG_TIMEOUT = 'timeout'
ERROR_TAG_CONNECTION = 'connection'
ERROR_TAG_SSL = 'ssl'
ERROR_TAG_ENCODING = 'encoding'
ERROR_TAG_HTTP = 'http'
ERROR_TAG_SYSTEM = 'system'
ERROR_TAG_UNKNOWN = 'unknown'
ERROR_TAGS = (
    (ERROR_TAG_TIMEOUT, 'Timeout'),
    (ERROR_TAG_CONNECTION, 'Connection Error'),
    (ERROR_TAG_SSL, 'SSL Error'),
    (ERROR_TAG_ENCODING, 'Encoding Error'),
    (ERROR_TAG_HTTP, 'HTTP Error'),
    (ERROR_TAG_SYSTEM, 'System Error'),
    (ERROR_TAG_UNKNOWN, 'Unknown Error'),
)

banned_headers = [
    re.compile(r'.*authorization.*', re.IGNORECASE),
    re.compile(r'.*cookie.*', re.IGNORECASE),
    re.compile(r'.*key.*', re.IGNORECASE),
    re.compile(r'.*token.*', re.IGNORECASE)
]


def _is_banned(s):
    for matcher in banned_headers:
        if matcher.match(s):
            return True
    return False


def _clean_headers(headers):
    return {
        k: v for k, v in headers.items() if not _is_banned(k) and not _is_banned(v)
    }


class CheckErrorQuerySet(models.QuerySet):
    def for_service(self, service):
        return self.filter(
            blockchain__service=service
        ).exclude(
            check_instance__completed__isnull=True
        )

    def get_error_counts(self, distance=datetime.timedelta(days=7)):
        tick_time_format = '%y-%m-%d %H:00'
        now = timezone.now()
        then = now - distance
        counts = self.filter(created__gt=then).annotate(
            started_hour=Trunc('created', 'hour'),
        ).values('tag', 'started_hour').annotate(errors=Count('tag'))
        seen_tags = set()
        hour_buckets = defaultdict(dict)
        for agg in counts:
            seen_tags.add(agg['tag'])
            hour_buckets[agg['tag']][agg['started_hour'].strftime(tick_time_format)] = agg['errors']
        hours = int(distance.total_seconds() / 60 / 60)
        ticks = {'labels': [], 'data': defaultdict(list)}
        for i in range(hours, -1, -1):
            date = (now - datetime.timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            tick_date = date.strftime(tick_time_format)
            ticks['labels'].append(tick_date)
            for tag in seen_tags:
                value = hour_buckets[tag].get(tick_date, 0)
                ticks['data'][tag].append(value)
        return ticks


class CheckError(models.Model):
    check_instance = models.ForeignKey(CheckInstance, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, null=True, on_delete=models.CASCADE)
    blockchain = models.ForeignKey(Blockchain, null=True, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=4, default='')
    url = models.CharField(max_length=2048, default='')
    request_headers = models.JSONField(default=dict)
    request_body = models.TextField(default='')
    status_code = models.IntegerField(default=-1)
    response_headers = models.JSONField(default=dict)
    response_body = models.TextField(default='')
    error_message = models.TextField()
    traceback = models.TextField(default='')
    tag = models.CharField(choices=ERROR_TAGS, max_length=10, default=ERROR_TAG_UNKNOWN)

    objects = CheckErrorQuerySet.as_manager()

    def __str__(self):
        return self.error_message

    def blockchain_slug(self):
        return self.blockchain.slug if self.blockchain is not None else 'n/a'

    blockchain_slug.short_description = 'Blockchain'

    def service_slug(self):
        return self.blockchain.service.slug if self.service is None else self.service.slug

    service_slug.short_description = 'Service'

    def error_message_truncated(self):
        if len(self.error_message) > 50:
            return self.error_message[:50] + '...'
        return self.error_message

    error_message_truncated.short_description = 'Message'

    def request_headers_cleaned(self):
        return _clean_headers(self.request_headers)

    def response_headers_cleaned(self):
        return _clean_headers(self.request_headers)

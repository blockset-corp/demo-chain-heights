from django.db import models
from autoslug import AutoSlugField

CHECK_TYPE_BLOCK_HEIGHT = 'bh'
CHECK_TYPES = (
    (CHECK_TYPE_BLOCK_HEIGHT, 'Block Height'),
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

    def __str__(self):
        return self.name


class Blockchain(models.Model):
    name = models.CharField(max_length=60)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    slug = models.CharField(max_length=60)
    is_testnet = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=('service', 'slug'), name='service_blockchain_slug')
        ]

    def __str__(self):
        return f'{self.service} {self.name}'


class CheckInstance(models.Model):
    type = models.CharField(choices=CHECK_TYPES, max_length=2, db_column='check_type')
    started = models.DateTimeField()
    completed = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=('type', 'completed'), name='check_type_completed')
        ]

    def __str__(self):
        s = f'{self.type} {self.started}'
        if self.completed:
            dur = self.completed - self.started
            s = s + f' {dur}'
        return s


class ChainHeightResult(models.Model):
    blockchain = models.ForeignKey(Blockchain, on_delete=models.CASCADE)
    check_instance = models.ForeignKey(CheckInstance, on_delete=models.CASCADE)
    started = models.DateTimeField()
    duration = models.IntegerField(help_text='Duration in nanoseconds')
    status = models.CharField(max_length=2, choices=RESULT_STATUSES)
    height = models.IntegerField(default=0)
    error = models.TextField(default='')

    def __str__(self):
        return f'{self.blockchain} {self.get_status_display()} {self.height}'

    def service_slug(self):
        return self.blockchain.service.slug

    def blockchain_slug(self):
        return self.blockchain.slug

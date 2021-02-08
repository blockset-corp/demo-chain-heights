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


class CheckResult(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField()
    duration = models.IntegerField()
    check_type = models.CharField(max_length=2, choices=CHECK_TYPES)
    status = models.CharField(max_length=2, choices=RESULT_STATUSES)
    request = models.JSONField()
    response = models.JSONField()

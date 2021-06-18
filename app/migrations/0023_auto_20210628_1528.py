# Generated by Django 3.1.6 on 2021-06-28 15:28

from django.db import migrations


def create_prune_old_results_task(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=1, period='days'
    )

    PeriodicTask.objects.create(
        interval=schedule,
        name='Prune old service results',
        task='app.tasks.prune_old_results'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0022_auto_20210625_0440'),
    ]

    operations = [
        migrations.RunPython(create_prune_old_results_task)
    ]

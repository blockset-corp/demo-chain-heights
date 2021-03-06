# Generated by Django 3.1.6 on 2021-02-11 00:08

from django.db import migrations


def create_services(apps, schema_editor):
    Service = apps.get_model('app', 'Service')
    Service.objects.create(name='Blockset Node', slug='blocksetnode')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0012_auto_20210210_2328'),
    ]

    operations = [
        migrations.RunPython(create_services)
    ]

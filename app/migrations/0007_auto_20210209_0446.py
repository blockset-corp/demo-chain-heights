# Generated by Django 3.1.6 on 2021-02-09 04:46

from django.db import migrations


def create_services(apps, schema_editor):
    Service = apps.get_model('app', 'Service')
    Service.objects.create(name='Blockchain.info', slug='blockchain')
    Service.objects.create(name='Etherscan', slug='etherscan')
    Service.objects.create(name='BlockCypher', slug='blockcypher')
    Service.objects.create(name='Blockchair', slug='blockchair')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_auto_20210209_0351'),
    ]

    operations = [
        migrations.RunPython(create_services)
    ]

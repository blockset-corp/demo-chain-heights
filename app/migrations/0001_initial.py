# Generated by Django 3.1.6 on 2021-02-08 16:45

import autoslug.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60)),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name')),
            ],
        ),
        migrations.CreateModel(
            name='CheckResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('started', models.DateTimeField()),
                ('duration', models.IntegerField()),
                ('check_type', models.CharField(choices=[('bh', 'Block Height')], max_length=2)),
                ('status', models.CharField(choices=[('ok', 'Ok'), ('er', 'Error'), ('wr', 'Warn')], max_length=2)),
                ('request', models.JSONField()),
                ('response', models.JSONField()),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.service')),
            ],
        ),
    ]

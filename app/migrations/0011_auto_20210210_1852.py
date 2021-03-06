# Generated by Django 3.1.6 on 2021-02-10 18:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_auto_20210210_0411'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='bulk_chain_query',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='chainheightresult',
            name='check_instance',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='app.checkinstance'),
        ),
    ]

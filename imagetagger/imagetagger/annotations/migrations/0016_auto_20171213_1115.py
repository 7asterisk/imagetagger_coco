# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-12-13 10:15
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0015_auto_20171129_1511'),
    ]

    operations = [
        migrations.AlterField(
            model_name='export',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
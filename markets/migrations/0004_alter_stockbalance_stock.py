# Generated by Django 3.2.10 on 2024-01-22 13:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0003_rename_symbol_transaction_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockbalance',
            name='stock',
            field=models.CharField(max_length=30),
        ),
    ]

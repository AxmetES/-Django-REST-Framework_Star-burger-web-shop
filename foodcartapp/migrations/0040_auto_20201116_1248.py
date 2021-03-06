# Generated by Django 3.0.7 on 2020-11-16 12:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodcartapp', '0039_orderdetails_product_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_status',
            field=models.CharField(choices=[('NP', 'not processed'), ('P', 'processed')], default='NP', max_length=2),
        ),
        migrations.AlterField(
            model_name='orderdetails',
            name='product_price',
            field=models.FloatField(null=True, verbose_name='сумма цен продукта'),
        ),
    ]

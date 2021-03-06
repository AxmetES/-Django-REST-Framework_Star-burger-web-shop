from datetime import date

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
import requests
from environs import Env
from geopy import distance
from django.core.cache import cache

env = Env()
env.read_env()

apikey = env('geo_api')


def fetch_coordinates(apikey, place):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    params = {"geocode": place, "apikey": apikey, "format": "json"}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    places_found = response.json()['response']['GeoObjectCollection']['featureMember']
    most_relevant = places_found[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


class Restaurant(models.Model):
    name = models.CharField('название', max_length=50)
    address = models.CharField('адрес', max_length=100, blank=True)
    contact_phone = models.CharField('контактный телефон', max_length=50, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.distinct().filter(menu_items__availability=True)


class ProductCategory(models.Model):
    name = models.CharField('название', max_length=50)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('название', max_length=50)
    category = models.ForeignKey(ProductCategory, null=True, blank=True, on_delete=models.SET_NULL,
                                 verbose_name='категория', related_name='products')
    price = models.DecimalField('цена', max_digits=8, decimal_places=2)
    image = models.ImageField('картинка')
    special_status = models.BooleanField('спец.предложение', default=False, db_index=True)
    description = models.TextField('описание', max_length=200, blank=True)

    objects = ProductQuerySet.as_manager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'


class Order(models.Model):
    NOT_PROCESSED = 'необработанный'
    PROCESSED = 'обработанный'
    ORDER_STATUS = [
        (NOT_PROCESSED, 'not processed'),
        (PROCESSED, 'processed'),
    ]
    CART_PAYMENT = 'оплата картой'
    CASH_PAYMENT = 'оплата наличными'
    PAYMENT_METHOD = [
        (CART_PAYMENT, 'оплата картой'),
        (PROCESSED, 'processed'),
    ]
    order_status = models.CharField(max_length=14, choices=ORDER_STATUS, default=NOT_PROCESSED)
    payment_method = models.CharField(max_length=13, choices=PAYMENT_METHOD, default=CART_PAYMENT)
    firstname = models.CharField(max_length=50, verbose_name='имя')
    lastname = models.CharField(max_length=50, verbose_name='фамилия')
    address = models.CharField(max_length=100, verbose_name='адресс')
    phonenumber = models.CharField(max_length=10, verbose_name='номер телефона')
    comment = models.TextField(verbose_name='комментарии', blank=True)
    timestamp = models.DateTimeField(default=date.today(), blank=True, null=True)
    call_time = models.DateTimeField(blank=True, null=True)
    delivery_time = models.DateTimeField(blank=True, null=True)

    def get_order_price_sum(self):
        order_sum = Order.objects.filter(pk=self.id).aggregate(order_price_sum=Sum('details__product_price'))
        return order_sum['order_price_sum']

    def get_restaurant_distance(self):
        rest_distance = set()
        order_details = self.details.prefetch_related('product')
        products_id = [detail.product_id for detail in order_details]

        for product_id in products_id:
            rest_queryset = RestaurantMenuItem.objects.prefetch_related('restaurant').filter(product__id=product_id)
            for rest in rest_queryset:
                restaurant_distance = cache.get(rest.restaurant.name)
                if not restaurant_distance:
                    restaurant_distance = distance.distance(
                        fetch_coordinates(apikey, f"{rest.restaurant.name},{rest.restaurant.address}"),
                        fetch_coordinates(apikey, self.address)).km
                    cache.set(rest.restaurant.name, restaurant_distance, 300)

                rest_distance.add(
                    f"{rest.restaurant.name} - {format(restaurant_distance, '.2f')} km,"
                )
        return f"{' '.join(str(s) for s in rest_distance)}"

    def __str__(self):
        template = f'{self.firstname} {self.lastname}'
        return template

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'


class OrderDetails(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='products', verbose_name='продукт')
    quantity = models.IntegerField('количество', validators=[MinValueValidator(1), MaxValueValidator(100)])
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='details', verbose_name='заказ')
    product_price = models.FloatField('сумма цен продукта', null=True)

    def __str__(self):
        template = f'{self.product}, {self.order}'
        return template

    class Meta:
        verbose_name = 'деталь заказа'
        verbose_name_plural = 'детали заказа'


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='menu_items')
    availability = models.BooleanField('в продаже', default=True, db_index=True)

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

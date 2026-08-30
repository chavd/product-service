from decimal import Decimal

import factory

from catalog.models import Category, Product


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f'Category {n}')
    slug = factory.Sequence(lambda n: f'category-{n}')
    parent = None


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    sku = factory.Sequence(lambda n: f'SKU-{n:05d}')
    title = 'Generic Product'
    description = ''
    price = Decimal('9.99')
    category = factory.SubFactory(CategoryFactory)
    is_active = True

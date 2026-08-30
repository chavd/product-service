"""Fixtures for the search tests.

The tree mirrors the one in 05-tests.md, because the interesting category
case is a grandchild: a product filed three levels down still has to show up
when the top-level category is queried.

    Electronics
    ├── Laptops
    │   ├── Gaming Laptops   ← LAP-001
    │   └── Ultrabooks       ← LAP-002
    └── Phones               ← PHN-001
    Clothing                 ← CLO-001, DSC-001, DEC-001, OLD-001
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from .factories import CategoryFactory, ProductFactory


@pytest.fixture
def tree(db):
    electronics = CategoryFactory(name='Electronics', slug='electronics')
    laptops = CategoryFactory(name='Laptops', slug='laptops', parent=electronics)
    gaming = CategoryFactory(name='Gaming Laptops', slug='gaming-laptops', parent=laptops)
    ultrabooks = CategoryFactory(name='Ultrabooks', slug='ultrabooks', parent=laptops)
    phones = CategoryFactory(name='Phones', slug='phones', parent=electronics)
    clothing = CategoryFactory(name='Clothing', slug='clothing')

    return SimpleNamespace(
        electronics=electronics,
        laptops=laptops,
        gaming=gaming,
        ultrabooks=ultrabooks,
        phones=phones,
        clothing=clothing,
    )


@pytest.fixture
def products(tree):
    items = SimpleNamespace(
        gaming_laptop=ProductFactory(
            sku='LAP-001',
            title='Gaming Laptop Pro',
            price=Decimal('1500.00'),
            category=tree.gaming,
        ),
        ultrabook=ProductFactory(
            sku='LAP-002',
            title='Ultrabook Laptop Air',
            price=Decimal('1000.00'),
            category=tree.ultrabooks,
        ),
        phone=ProductFactory(
            sku='PHN-001',
            title='Smartphone X',
            price=Decimal('500.00'),
            category=tree.phones,
        ),
        shirt=ProductFactory(
            sku='CLO-001',
            title='Cotton Shirt',
            price=Decimal('20.00'),
            category=tree.clothing,
        ),
        # Title says nothing about laptops, the description does — this is
        # what the ranking assertion compares against.
        mouse=ProductFactory(
            sku='DSC-001',
            title='Wireless Mouse',
            description='A comfortable mouse for laptop users.',
            price=Decimal('30.00'),
            category=tree.clothing,
        ),
        # Exactly on a price boundary. A float-backed column would make this
        # assertion flaky; NUMERIC does not.
        boundary=ProductFactory(
            sku='DEC-001',
            title='Boundary Item',
            price=Decimal('19.99'),
            category=tree.clothing,
        ),
        inactive=ProductFactory(
            sku='OLD-001',
            title='Discontinued Laptop',
            price=Decimal('800.00'),
            category=tree.clothing,
            is_active=False,
        ),
    )

    # created_at is auto_now_add, so it has to be overwritten afterwards.
    # Fixed timestamps keep ordering assertions independent of the clock.
    base = timezone.datetime(2026, 1, 1, 12, 0, tzinfo=timezone.get_current_timezone())
    for offset, product in enumerate(vars(items).values()):
        type(product).objects.filter(pk=product.pk).update(
            created_at=base + timezone.timedelta(minutes=offset)
        )

    return items

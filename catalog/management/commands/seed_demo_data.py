"""Idempotent demo data for the presentation.

Runs on every container start via the entrypoint, so it must never create
duplicates. Everything is keyed on the natural identifier — slug for
categories, SKU for products — and written with get_or_create.
"""

import os
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from catalog.models import Category, Currency, Product

# Three levels deep, so the recursive category search has something to
# recurse through: Electronics > Computers > Laptops.
CATEGORY_TREE = {
    'Electronics': {
        'Computers': ['Laptops', 'Tablets'],
        'Audio': ['Headphones', 'Speakers'],
    },
    'Home': {
        'Kitchen': ['Coffee Machines', 'Cookware'],
        'Cleaning': ['Vacuum Cleaners', 'Cleaning Supplies'],
    },
}

# Titles are deliberately similar within a family ("Aurora Laptop Pro 14"
# and "Aurora Laptop Pro 16"), which is what makes the trigram search
# demo meaningful — plain LIKE cannot rank these sensibly.
PRODUCTS = [
    # (sku, title, category slug, price, active)
    ('AUR-LP-PRO-14', 'Aurora Laptop Pro 14', 'laptops', '1899.00', True),
    ('AUR-LP-PRO-16', 'Aurora Laptop Pro 16', 'laptops', '2299.00', True),
    ('AUR-LP-AIR-13', 'Aurora Laptop Air 13', 'laptops', '1199.00', True),
    ('AUR-LP-AIR-15', 'Aurora Laptop Air 15', 'laptops', '1399.00', True),
    ('NOV-LP-STU-15', 'Nova Laptop Studio 15', 'laptops', '1649.00', True),
    ('ZEN-LP-BAS-14', 'Zenith Laptop Basic 14', 'laptops', '649.00', True),
    ('AUR-LP-PRO-13', 'Aurora Laptop Pro 13', 'laptops', '1749.00', False),

    ('AUR-TB-PRO-11', 'Aurora Tablet Pro 11', 'tablets', '899.00', True),
    ('AUR-TB-MIN-08', 'Aurora Tablet Mini 8', 'tablets', '499.00', True),
    ('NOV-TB-STU-11', 'Nova Tablet Studio 11', 'tablets', '749.00', True),
    ('ZEN-TB-BAS-10', 'Zenith Tablet Basic 10', 'tablets', '229.00', True),

    ('SON-HP-ANC-01', 'Sonic Headphones ANC Elite', 'headphones', '349.00', True),
    ('SON-HP-ANC-02', 'Sonic Headphones ANC Lite', 'headphones', '199.00', True),
    ('SON-HP-STU-03', 'Sonic Headphones Studio', 'headphones', '279.00', True),
    ('ECH-HP-BUD-01', 'Echo Earbuds Pro', 'headphones', '149.00', True),
    ('ECH-HP-BUD-02', 'Echo Earbuds Lite', 'headphones', '79.00', True),

    ('ECH-SP-ROO-01', 'Echo Room Speaker 200', 'speakers', '229.00', True),
    ('ECH-SP-ROO-02', 'Echo Room Speaker 400', 'speakers', '399.00', True),
    ('BAS-SP-POR-01', 'Basspod Portable Speaker', 'speakers', '129.00', True),
    ('BAS-SP-POR-02', 'Basspod Portable Speaker Mini', 'speakers', '89.00', True),

    ('BRW-CM-AUT-08', 'Brewmaster Automatic 800', 'coffee-machines', '749.00', True),
    ('BRW-CM-AUT-12', 'Brewmaster Automatic 1200', 'coffee-machines', '1099.00', True),
    ('BRW-CM-MAN-01', 'Brewmaster Manual Espresso', 'coffee-machines', '449.00', True),
    ('DRP-CM-FIL-12', 'Dripline Filter Coffee 12', 'coffee-machines', '89.00', True),

    ('IRN-CW-PAN-24', 'Ironcast Pan 24 cm', 'cookware', '59.00', True),
    ('IRN-CW-PAN-28', 'Ironcast Pan 28 cm', 'cookware', '69.00', True),
    ('IRN-CW-POT-05', 'Ironcast Pot 5 L', 'cookware', '99.00', True),
    ('STL-CW-SET-10', 'Steelline Cookware Set 10 pcs', 'cookware', '249.00', True),

    ('WHR-VC-COR-01', 'Whirl Vacuum Cordless S', 'vacuum-cleaners', '299.00', True),
    ('WHR-VC-COR-02', 'Whirl Vacuum Cordless XL', 'vacuum-cleaners', '449.00', True),
    ('WHR-VC-ROB-05', 'Whirl Robot Vacuum R5', 'vacuum-cleaners', '599.00', True),
    ('DST-VC-CAN-20', 'Dustaway Canister 2000W', 'vacuum-cleaners', '159.00', True),

    ('DST-AC-BAG-10', 'Dustaway Dust Bags 10 pack', 'cleaning-supplies', '12.99', True),
    ('DST-AC-FIL-02', 'Dustaway HEPA Filter', 'cleaning-supplies', '24.50', True),
]

DESCRIPTION = (
    'Demo record created by seed_demo_data. Not a real product; the text is '
    'here so that description search has something to match against.'
)


def slugify_name(name):
    return name.lower().replace(' ', '-')


def placeholder_image(label):
    """A small generated PNG, so the image field is not empty in the demo."""
    image = Image.new('RGB', (400, 400), (37, 47, 63))
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 387, 387), outline=(120, 140, 170), width=3)
    draw.text((28, 190), label, fill=(235, 240, 248))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue(), name=f'{label.lower()}.png')


class Command(BaseCommand):
    help = 'Create demo categories, products and a superuser. Safe to re-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-images',
            action='store_true',
            help='Generate a placeholder image for every product that has none.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        categories = self._seed_categories()
        created = self._seed_products(categories, options['with_images'])
        self._seed_superuser()

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {Category.objects.count()} categories, '
            f'{Product.objects.count()} products ({created} newly created).'
        ))

    def _seed_categories(self):
        by_slug = {}

        for top, middles in CATEGORY_TREE.items():
            top_obj = self._category(top, parent=None)
            by_slug[top_obj.slug] = top_obj

            for middle, leaves in middles.items():
                middle_obj = self._category(middle, parent=top_obj)
                by_slug[middle_obj.slug] = middle_obj

                for leaf in leaves:
                    leaf_obj = self._category(leaf, parent=middle_obj)
                    by_slug[leaf_obj.slug] = leaf_obj

        return by_slug

    def _category(self, name, parent):
        obj, _ = Category.objects.get_or_create(
            slug=slugify_name(name),
            defaults={'name': name, 'parent': parent},
        )
        return obj

    def _seed_products(self, categories, with_images):
        created_count = 0

        for sku, title, category_slug, price, is_active in PRODUCTS:
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'title': title,
                    'description': DESCRIPTION,
                    'price': Decimal(price),
                    'currency': Currency.EUR,
                    'category': categories[category_slug],
                    'is_active': is_active,
                },
            )
            created_count += int(created)

            if with_images and not product.image:
                product.image.save(f'{sku}.png', placeholder_image(sku), save=True)

        return created_count

    def _seed_superuser(self):
        user_model = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

        if user_model.objects.filter(username=username).exists():
            return

        user_model.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.WARNING(
            f'Created superuser "{username}" — development credentials, change them anywhere else.'
        ))

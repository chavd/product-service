from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from .querysets import CategoryQuerySet, ProductQuerySet


class Currency(models.TextChoices):
    EUR = "EUR", "Euro"
    USD = "USD", "US-Dollar"
    GBP = "GBP", "Britisches Pfund"
    BGN = "BGN", "Bulgarischer Lew"


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True, null=True)
    # The validator turns a negative price into a 400 with a readable message.
    # The CheckConstraint below stays as the guarantee — it also covers the
    # paths that skip validation, such as bulk inserts and shell access.
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        # Decimal, not int — DRF builds its own DecimalField from this and
        # warns when the bound is a different numeric type.
        validators=[MinValueValidator(Decimal('0'))],
    )
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.EUR)
    category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        indexes = [
            # Trigram indexes for the fuzzy search. gin_trgm_ops requires
            # pg_trgm, installed in migration 0003.
            GinIndex(
                name='idx_prod_title_trgm',
                fields=['title'],
                opclasses=['gin_trgm_ops'],
            ),
            GinIndex(
                name='idx_prod_sku_trgm',
                fields=['sku'],
                opclasses=['gin_trgm_ops'],
            ),
            models.Index(
                fields=["category", "-created_at"],
                condition=Q(is_active=True),
                name="idx_prod_active_cat_created",
            ),
            models.Index(
                fields=["price"],
                condition=Q(is_active=True),
                name="idx_prod_price",
            ),
            models.Index(
                fields=["-created_at", "-id"],
                condition=Q(is_active=True),
                name="idx_prod_created_id",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="product_price_non_negative",
            ),
        ]

    def __str__(self):
        return self.sku

    def save(self, *args, **kwargs):
        self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True, blank=True,
        related_name="children",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CategoryQuerySet.as_manager()

    def __str__(self):
        return self.name

    def clean(self):
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                raise ValidationError({"parent": "A category cannot be its own ancestor."})
            ancestor = ancestor.parent
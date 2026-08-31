from decimal import Decimal

import django_filters
from django import forms

from .models import Category, Currency, Product


class ProductFilterForm(forms.Form):
    """Cross-field validation for the query string.

    An impossible range is a client mistake, not an empty result set — the
    difference between "you asked wrongly" and "nothing matched" is exactly
    what a caller needs to debug their request.
    """

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get('price_min')
        maximum = cleaned.get('price_max')

        if minimum is not None and maximum is not None and minimum > maximum:
            raise forms.ValidationError(
                {'price_min': 'price_min must not be greater than price_max.'}
            )

        return cleaned


class ProductFilterSet(django_filters.FilterSet):
    # Public parameter names avoid the double underscore of the ORM lookup
    # syntax. The API surface should not leak how it is implemented.
    q = django_filters.CharFilter(
        method='filter_q',
        label='Free text over title, SKU and description',
    )
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    sku = django_filters.CharFilter(method='filter_sku')

    price_min = django_filters.NumberFilter(
        field_name='price', lookup_expr='gte', min_value=Decimal('0'),
    )
    price_max = django_filters.NumberFilter(
        field_name='price', lookup_expr='lte', min_value=Decimal('0'),
    )

    category = django_filters.CharFilter(
        method='filter_category',
        label='Category id or slug',
    )
    include_descendants = django_filters.BooleanFilter(
        method='filter_noop',
        label='Include subcategories (default true)',
    )

    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label='Include soft-deleted products (default: only active ones)',
    )

    currency = django_filters.ChoiceFilter(choices=Currency.choices)
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='gte',
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='lte',
    )

    class Meta:
        model = Product
        fields = []

    @property
    def form(self):
        # django-filter builds its form lazily; swapping the class in here is
        # what gets the cross-field clean() above to run.
        if not hasattr(self, '_form'):
            form_class = self.get_form_class()
            bound = type(form_class.__name__, (ProductFilterForm, form_class), {})
            self._form = bound(data=self.data, prefix=self.form_prefix)
        return self._form

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        # django-filter skips a filter whose parameter is absent, but the
        # default here is not "no filter" — soft-deleted products stay out
        # unless the caller asks for them by name.
        if self.form.cleaned_data.get('is_active') is None:
            queryset = queryset.active()

        return queryset

    def filter_noop(self, queryset, name, value):
        """include_descendants is read inside filter_category."""
        return queryset

    def filter_q(self, queryset, name, value):
        return queryset.search(value)

    def filter_sku(self, queryset, name, value):
        # SKUs are stored normalised, so the lookup normalises too.
        return queryset.filter(sku=value.strip().upper())

    def filter_category(self, queryset, name, value):
        value = value.strip()
        lookup = {'pk': value} if value.isdigit() else {'slug': value}

        category = Category.objects.filter(**lookup).first()
        if category is None:
            return queryset.none()

        include = self.form.cleaned_data.get('include_descendants')
        if include is None:
            include = True

        return queryset.in_category(category.pk, include_descendants=include)

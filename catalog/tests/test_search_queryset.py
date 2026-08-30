"""Search logic without HTTP.

If one of these fails, the query logic is wrong. If only the API tests fail,
the parameter mapping is wrong — that separation is the point of testing on
two levels.
"""

from decimal import Decimal

import pytest

from catalog.models import Product

pytestmark = pytest.mark.django_db


def skus(queryset):
    return sorted(product.sku for product in queryset)


@pytest.mark.parametrize(
    'term,expected',
    [
        # Both laptops match: LAP-002 is "Ultrabook Laptop Air", a genuine
        # near miss rather than noise.
        ('Gaming Laptop Pro', ['LAP-001', 'LAP-002']),
        ('Ultrabook', ['LAP-002']),
        ('LAPTOP', ['DSC-001', 'LAP-001', 'LAP-002']),   # case-insensitive
        ('laptop', ['DSC-001', 'LAP-001', 'LAP-002']),   # also the description hit
        ('lpatop', ['LAP-001', 'LAP-002']),              # transposed letters
        ('comfortable', ['DSC-001']),                    # description only
        ('xyzzy', []),                                   # no match is empty, not everything
    ],
)
def test_search_matches(products, term, expected):
    assert skus(Product.objects.active().search(term)) == expected


def test_exact_sku_finds_the_product(products):
    result = skus(Product.objects.active().search('LAP-001'))
    assert 'LAP-001' in result
    # Unrelated identifiers must not ride along just because SKUs share a
    # shape — that is what the strict SKU threshold is for.
    assert 'PHN-001' not in result
    assert 'CLO-001' not in result


def test_search_finds_description_hit(products):
    # 'mouse' appears only in a title, 'comfortable' only in a description.
    assert skus(Product.objects.active().search('comfortable')) == ['DSC-001']


def test_title_hit_outranks_description_hit(products):
    """Ranking, not absolute scores.

    Asserting on a similarity value would tie the test to a Postgres version.
    The ordering is the part that carries meaning.
    """
    results = list(
        Product.objects.active().search('laptop').order_by('-relevance', '-id')
    )

    positions = {product.sku: index for index, product in enumerate(results)}
    assert positions['LAP-001'] < positions['DSC-001']
    assert positions['LAP-002'] < positions['DSC-001']


@pytest.mark.parametrize('term', ['', '   ', None])
def test_blank_term_is_not_a_filter(products, term):
    assert Product.objects.active().search(term).count() == 6


@pytest.mark.parametrize('term', ['%', '_', "'", 'ümlaut', "'; DROP TABLE catalog_product; --"])
def test_special_characters_do_not_break_the_query(products, term):
    # The ORM parameterises, so these are values and never syntax. Running
    # them proves the wildcard characters are not treated as patterns either.
    Product.objects.active().search(term).count()
    assert Product.objects.count() == 7


def test_short_term_does_not_crash(products):
    # Under three characters there are barely any trigrams; the documented
    # behaviour is "whatever icontains finds", not an error.
    Product.objects.active().search('ab').count()


class TestPriceRange:
    def test_minimum_is_inclusive(self, products):
        result = Product.objects.active().in_price_range(minimum=Decimal('19.99'))
        assert 'DEC-001' in skus(result)

    def test_maximum_is_inclusive(self, products):
        result = Product.objects.active().in_price_range(maximum=Decimal('19.99'))
        assert skus(result) == ['DEC-001']

    def test_both_bounds(self, products):
        result = Product.objects.active().in_price_range(
            minimum=Decimal('500.00'), maximum=Decimal('1000.00')
        )
        assert skus(result) == ['LAP-002', 'PHN-001']

    def test_excludes_outside_the_range(self, products):
        result = Product.objects.active().in_price_range(maximum=Decimal('100.00'))
        assert 'LAP-001' not in skus(result)


class TestCategory:
    def test_descendants_included_by_default(self, products, tree):
        """The most important test of the assignment.

        Electronics holds no products directly — they all sit two and three
        levels below it. A plain filter(category_id=...) returns nothing here.
        """
        result = Product.objects.active().in_category(tree.electronics.pk)
        assert skus(result) == ['LAP-001', 'LAP-002', 'PHN-001']

    def test_without_descendants_only_the_direct_level(self, products, tree):
        result = Product.objects.active().in_category(
            tree.electronics.pk, include_descendants=False
        )
        assert skus(result) == []

    def test_intermediate_level_collects_its_subtree(self, products, tree):
        result = Product.objects.active().in_category(tree.laptops.pk)
        assert skus(result) == ['LAP-001', 'LAP-002']

    def test_leaf_category_works(self, products, tree):
        result = Product.objects.active().in_category(tree.gaming.pk)
        assert skus(result) == ['LAP-001']

    def test_siblings_are_excluded(self, products, tree):
        result = Product.objects.active().in_category(tree.electronics.pk)
        assert 'CLO-001' not in skus(result)

    def test_unknown_category_is_empty(self, products):
        assert skus(Product.objects.active().in_category(999_999)) == []


def test_filters_combine_with_and(products, tree):
    result = (
        Product.objects.active()
        .search('laptop')
        .in_price_range(minimum=Decimal('1200.00'))
        .in_category(tree.electronics.pk)
    )
    assert skus(result) == ['LAP-001']


def test_soft_deleted_products_are_excluded(products):
    assert 'OLD-001' not in skus(Product.objects.active().search('laptop'))
    assert 'OLD-001' in skus(Product.objects.search('laptop'))

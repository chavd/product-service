"""The thin layer above the query logic: parameter mapping, status codes and
response shape."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

URL = '/api/v1/products/'


@pytest.fixture
def client():
    return APIClient()


def result_skus(response):
    return sorted(row['sku'] for row in response.data['results'])


def test_query_parameter_reaches_the_search(client, products):
    response = client.get(URL, {'q': 'ultrabook'})
    assert response.status_code == 200
    assert result_skus(response) == ['LAP-002']


def test_category_filter_is_recursive_over_the_api(client, products):
    response = client.get(URL, {'category': 'electronics'})
    assert result_skus(response) == ['LAP-001', 'LAP-002', 'PHN-001']


def test_include_descendants_false_narrows_to_one_level(client, products):
    response = client.get(URL, {'category': 'electronics', 'include_descendants': 'false'})
    assert result_skus(response) == []


def test_category_accepts_an_id_as_well_as_a_slug(client, products, tree):
    by_slug = client.get(URL, {'category': 'laptops'})
    by_id = client.get(URL, {'category': str(tree.laptops.pk)})
    assert result_skus(by_slug) == result_skus(by_id) == ['LAP-001', 'LAP-002']


def test_price_range_maps_through(client, products):
    response = client.get(URL, {'price_min': '500', 'price_max': '1000'})
    assert result_skus(response) == ['LAP-002', 'PHN-001']


@pytest.mark.parametrize(
    'params,field',
    [
        ({'price_min': '1500', 'price_max': '500'}, 'price_min'),
        ({'price_min': 'abc'}, 'price_min'),
        ({'price_min': '-5'}, 'price_min'),
        ({'currency': 'XYZ'}, 'currency'),
    ],
)
def test_invalid_filters_are_rejected(client, products, params, field):
    """400, not a silently empty list.

    Degrading an unparseable filter to "no filter" hands the caller wrong
    results without telling them.
    """
    response = client.get(URL, params)
    assert response.status_code == 400
    assert field in response.data


def test_legitimately_empty_result_is_200(client, products):
    response = client.get(URL, {'q': 'laptop', 'price_max': '1'})
    assert response.status_code == 200
    assert response.data['count'] == 0


class TestOrdering:
    def test_ascending_and_descending(self, client, products):
        ascending = client.get(URL, {'ordering': 'price'})
        descending = client.get(URL, {'ordering': '-price'})

        # Decimal, not the string the serializer renders — "19.99" sorts
        # before "500.00" lexicographically, which would make this pass for
        # the wrong reason.
        prices = [Decimal(row['price']) for row in ascending.data['results']]
        assert prices == sorted(prices)
        assert [Decimal(row['price']) for row in descending.data['results']] == prices[::-1]

    def test_field_outside_the_whitelist_is_ignored(self, client, products):
        response = client.get(URL, {'ordering': 'id'})
        assert response.status_code == 200

    def test_relevance_without_a_query_does_not_error(self, client, products):
        # The relevance annotation only exists while q is set; accepting the
        # ordering unconditionally would raise a FieldError.
        response = client.get(URL, {'ordering': 'relevance'})
        assert response.status_code == 200

    def test_default_ordering_is_stable(self, client, products):
        first = [row['sku'] for row in client.get(URL).data['results']]
        second = [row['sku'] for row in client.get(URL).data['results']]
        assert first == second


class TestPagination:
    def test_pages_do_not_overlap(self, client, products):
        page_one = client.get(URL, {'page_size': '3', 'page': '1'})
        page_two = client.get(URL, {'page_size': '3', 'page': '2'})

        first = {row['sku'] for row in page_one.data['results']}
        second = {row['sku'] for row in page_two.data['results']}
        assert first & second == set()

    def test_page_size_is_capped(self, client, products, settings):
        response = client.get(URL, {'page_size': '10000'})
        assert len(response.data['results']) <= 100


class TestSoftDelete:
    def test_excluded_by_default(self, client, products):
        response = client.get(URL, {'q': 'laptop'})
        assert 'OLD-001' not in result_skus(response)

    def test_reachable_with_an_explicit_flag(self, client, products):
        response = client.get(URL, {'q': 'laptop', 'is_active': 'false'})
        assert result_skus(response) == ['OLD-001']

    def test_explicit_true_matches_the_default(self, client, products):
        explicit = client.get(URL, {'q': 'laptop', 'is_active': 'true'})
        implicit = client.get(URL, {'q': 'laptop'})
        assert result_skus(explicit) == result_skus(implicit)

    def test_detail_of_a_soft_deleted_product_is_404(self, client, products):
        assert client.get(f'{URL}OLD-001/').status_code == 404

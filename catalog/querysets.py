"""Query logic, deliberately kept out of the views.

Everything here is callable without HTTP, which is what makes the search
testable as plain query code rather than through the API surface.
"""

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db import connection, models
from django.db.models import Q
from django.db.models.functions import Greatest

# Word similarity, not plain similarity: the latter compares the term against
# the whole field, so a short query is structurally penalised by a long title.
# Measured against the seed data, searching the typo "aurroa":
#
#   similarity("Aurora Laptop Pro 14", "aurroa")       = 0.120
#   word_similarity("aurroa", "Aurora Laptop Pro 14")  = 0.429
#
# Calibrated on the same data: real typo hits score 0.43-0.67, while noise
# (an unrelated product, or a two-character term matching everything weakly)
# stays at or below 0.33.
RELEVANCE_THRESHOLD = 0.35

# Weights: a hit in the title matters more than one in the last paragraph
# of the description. Greatest, not a sum — a product should not rank high
# because one weak match occurs in three places.
TITLE_WEIGHT = 1.0
SKU_WEIGHT = 0.8
DESCRIPTION_WEIGHT = 0.3


class CategoryQuerySet(models.QuerySet):
    def descendant_ids(self, root_id):
        """Ids of a category and everything below it, via a recursive CTE.

        "Under a certain category" means recursively: asking for Electronics
        has to return products filed under Electronics > Computers > Laptops.

        UNION rather than UNION ALL is deliberate — it de-duplicates, so a
        cycle that slipped past the write-side checks terminates instead of
        looping forever.
        """
        table = self.model._meta.db_table
        sql = f"""
            WITH RECURSIVE subtree AS (
                SELECT id FROM {table} WHERE id = %s
                UNION
                SELECT c.id FROM {table} c
                JOIN subtree s ON c.parent_id = s.id
            )
            SELECT id FROM subtree
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [root_id])
            return [row[0] for row in cursor.fetchall()]


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def search(self, term):
        """Fuzzy search over title, SKU and description.

        Trigram similarity rather than icontains: a leading-wildcard ILIKE
        cannot use an index and gives every row the same score, so there is
        nothing to rank by.

        The extra icontains/iexact arm matters more than it looks. Terms
        shorter than three characters barely have trigrams, and an exact SKU
        lookup scores poorly against a long title — both would return nothing
        on similarity alone.
        """
        term = (term or '').strip()
        if not term:
            return self

        return self.annotate(
            relevance=Greatest(
                TrigramWordSimilarity(term, 'title') * TITLE_WEIGHT,
                TrigramWordSimilarity(term, 'sku') * SKU_WEIGHT,
                TrigramWordSimilarity(term, 'description') * DESCRIPTION_WEIGHT,
            )
        ).filter(
            Q(relevance__gt=RELEVANCE_THRESHOLD)
            | Q(title__icontains=term)
            | Q(sku__iexact=term)
        )

    def in_price_range(self, minimum=None, maximum=None):
        """Inclusive at both ends."""
        queryset = self
        if minimum is not None:
            queryset = queryset.filter(price__gte=minimum)
        if maximum is not None:
            queryset = queryset.filter(price__lte=maximum)
        return queryset

    def in_category(self, category_id, include_descendants=True):
        if not include_descendants:
            return self.filter(category_id=category_id)

        from .models import Category

        ids = Category.objects.descendant_ids(category_id)
        return self.filter(category_id__in=ids)

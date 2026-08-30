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
# Measured on the demo data, searching the typo "aurroa":
#
#   similarity("Aurora Laptop Pro 14", "aurroa")       = 0.120
#   word_similarity("aurroa", "Aurora Laptop Pro 14")  = 0.429
#
# Weights decide the ranking: a hit in the title is worth more than one in
# the last paragraph of a description. Greatest rather than a sum, so a
# product does not climb by matching weakly in three places at once.
TITLE_WEIGHT = 1.0
SKU_WEIGHT = 0.8
DESCRIPTION_WEIGHT = 0.3

# Thresholds decide membership, and they are per field on purpose. Applying
# one cut-off to the weighted score conflates "how well does this match" with
# "how much does this field count", and that combination misbehaves at both
# ends: a perfect description hit scores 1.0 * 0.3 and drops out, while
# unrelated SKUs — which all look alike, because identifiers are structured —
# score 0.5 * 0.8 and flood in.
#
# Measured values behind each number:
#   title        a transposed-letter typo lands at 0.286, so the cut sits below
#   sku          "LAP-001" scores 1.0 on itself and 0.75 on its neighbour
#                LAP-002; near-exact is the only useful match here
#   description  a real hit scores 1.0, incidental word overlap around 0.39
TITLE_THRESHOLD = 0.25
SKU_THRESHOLD = 0.8
DESCRIPTION_THRESHOLD = 0.5


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
            title_similarity=TrigramWordSimilarity(term, 'title'),
            sku_similarity=TrigramWordSimilarity(term, 'sku'),
            description_similarity=TrigramWordSimilarity(term, 'description'),
            relevance=Greatest(
                TrigramWordSimilarity(term, 'title') * TITLE_WEIGHT,
                TrigramWordSimilarity(term, 'sku') * SKU_WEIGHT,
                TrigramWordSimilarity(term, 'description') * DESCRIPTION_WEIGHT,
            ),
        ).filter(
            Q(title_similarity__gt=TITLE_THRESHOLD)
            | Q(sku_similarity__gt=SKU_THRESHOLD)
            | Q(description_similarity__gt=DESCRIPTION_THRESHOLD)
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

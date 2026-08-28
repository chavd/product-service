from collections import defaultdict

from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('parent').order_by('name')
    serializer_class = CategorySerializer

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """The hierarchy as nested JSON.

        Built from a single query: fetch every category once, group by parent
        in memory, then assemble. Walking the tree with the ORM instead would
        cost one query per node.
        """
        by_parent = defaultdict(list)
        for category in Category.objects.order_by('name'):
            by_parent[category.parent_id].append(category)

        def build(parent_id):
            return [
                {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'children': build(category.id),
                }
                for category in by_parent[parent_id]
            ]

        return Response(build(None))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            # on_delete=PROTECT raises this when children or products still
            # reference the category. Unhandled it becomes a 500 — a server
            # error for what is a client mistake.
            children = instance.children.count()
            products = instance.products.count()
            return Response(
                {'detail': (
                    f'Category has {children} subcategories and {products} '
                    f'products and cannot be deleted.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductViewSet(viewsets.ModelViewSet):
    # select_related collapses what would otherwise be one extra query per
    # row for the embedded category.
    queryset = Product.objects.select_related('category').filter(is_active=True)
    serializer_class = ProductSerializer

    # The SKU is the identifier clients already know, and it keeps the API
    # decoupled from the database's autoincrement. The default router pattern
    # does not match dots, hence the explicit regex.
    lookup_field = 'sku'
    lookup_value_regex = '[A-Za-z0-9._-]+'

    def destroy(self, request, *args, **kwargs):
        """Soft delete — orders, carts and analytics may still reference this
        product, and a hard delete would tear holes in historical data."""
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

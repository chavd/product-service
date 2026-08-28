from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    """Flat representation — parent as an id.

    The nested view of the hierarchy is a separate endpoint
    (/categories/tree/), so the list stays paginatable and predictable.
    """

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'parent', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate_parent(self, value):
        # Model.clean() covers admin and forms, but DRF does not call
        # full_clean(), so the same rule has to be enforced here.
        if value is None:
            return value

        if self.instance is not None:
            ancestor = value
            while ancestor is not None:
                if ancestor.pk == self.instance.pk:
                    raise serializers.ValidationError(
                        'A category cannot be its own ancestor.'
                    )
                ancestor = ancestor.parent

        return value


class CategoryBriefSerializer(serializers.ModelSerializer):
    """Embedded inside a product, so the client does not have to fetch the
    category separately for every row."""

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class ProductSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
    )

    class Meta:
        model = Product
        fields = (
            'sku', 'title', 'description', 'image',
            'price', 'currency',
            'category', 'category_id',
            'is_active', 'created_at', 'updated_at',
        )
        read_only_fields = ('is_active', 'created_at', 'updated_at')

    def to_internal_value(self, data):
        # The SKU has to be normalised *before* field validation runs, not
        # after. The unique check compares byte for byte: submitting "abc-1"
        # while "ABC-1" exists would pass validation, and Model.save() would
        # then upper-case it into a duplicate key — a 500 for what is really
        # a 400.
        sku = data.get('sku') if hasattr(data, 'get') else None
        if isinstance(sku, str):
            # copy() keeps a QueryDict a mutable QueryDict and a dict a dict.
            data = data.copy()
            data['sku'] = sku.strip().upper()
        return super().to_internal_value(data)

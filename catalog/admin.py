from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    # The list shows parent.name, which would be one extra query per row.
    list_select_related = ('parent',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'title', 'price', 'currency', 'category', 'is_active')
    list_filter = ('is_active', 'currency', 'category')
    search_fields = ('sku', 'title')
    list_select_related = ('category',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

from rest_framework.filters import OrderingFilter


class CatalogOrderingFilter(OrderingFilter):
    """Ordering with a whitelist, plus relevance when there is something to
    be relevant to.

    `relevance` only exists as an annotation while `q` is set. Accepting it
    unconditionally would raise a FieldError on an otherwise valid request,
    so it joins the whitelist only when the annotation is actually there.
    """

    relevance_ordering = ['-relevance', '-created_at', '-id']

    def _has_query(self, request):
        return bool((request.query_params.get('q') or '').strip())

    def get_valid_fields(self, queryset, view, context=None):
        valid = list(super().get_valid_fields(queryset, view, context or {}))
        request = (context or {}).get('request')
        if request is not None and self._has_query(request):
            valid.append(('relevance', 'relevance'))
        return valid

    def get_ordering(self, request, queryset, view):
        explicit = super().get_ordering(request, queryset, view)
        default = list(self.get_default_ordering(view) or [])

        # Falling back to the default while searching means the caller did not
        # ask for a specific order — rank by match quality instead of by age.
        if self._has_query(request) and explicit == default:
            return self.relevance_ordering

        return explicit

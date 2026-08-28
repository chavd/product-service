from rest_framework.pagination import PageNumberPagination


class CatalogPagination(PageNumberPagination):
    """Page-number pagination with a ceiling on the page size.

    Without max_page_size a client can ask for ?page_size=100000 and pull the
    whole table in one request, which defeats the point of paginating.

    Page numbers are the pragmatic choice for a catalogue with a paged UI.
    The trade-off: large offsets get slow, because the database has to walk
    every skipped row, and the window shifts when records are inserted while
    a client pages through. Cursor pagination avoids both but cannot jump to
    page N.
    """

    page_size_query_param = 'page_size'
    max_page_size = 100

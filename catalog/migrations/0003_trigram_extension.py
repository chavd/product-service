from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Enable pg_trgm.

    Separate from the index migration on purpose: the GIN indexes below use
    gin_trgm_ops, which does not exist until this extension is installed.
    """

    dependencies = [
        ('catalog', '0002_alter_product_price'),
    ]

    operations = [
        TrigramExtension(),
    ]

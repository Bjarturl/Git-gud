import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('git_data', '0011_migrate_tags_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='legacy_tags',
        ),
    ]

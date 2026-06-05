from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("search", "0005_regex_unique_pattern"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="status",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("false_positive", "False positive"),
                    ("interesting", "Interesting"),
                ],
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="match",
            index=models.Index(fields=["status"], name="search_matc_status_idx"),
        ),
    ]

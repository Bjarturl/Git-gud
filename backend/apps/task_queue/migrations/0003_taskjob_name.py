from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("task_queue", "0002_taskworker_claim_expires_at_taskworker_model_claims"),
    ]

    operations = [
        migrations.AddField(
            model_name="taskjob",
            name="name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

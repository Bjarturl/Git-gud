from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('git_data', '0010_tag_model_user_tags_m2m'),
        ('search', '0009_backfill_match_repo_gist_base_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='regex',
            name='tags',
            field=models.ManyToManyField(
                blank=True,
                related_name='regexes',
                to='git_data.tag',
            ),
        ),
    ]

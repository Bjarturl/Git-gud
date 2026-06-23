from django.db import migrations


def migrate_tags_forward(apps, schema_editor):
    User = apps.get_model('git_data', 'User')
    Tag = apps.get_model('git_data', 'Tag')
    for user in User.objects.exclude(legacy_tags=[]).iterator():
        for tag_name in user.legacy_tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            user.tags.add(tag)


def migrate_tags_backward(apps, schema_editor):
    User = apps.get_model('git_data', 'User')
    for user in User.objects.prefetch_related('tags').iterator():
        user.legacy_tags = list(user.tags.values_list('name', flat=True))
        user.save(update_fields=['legacy_tags'])


class Migration(migrations.Migration):

    dependencies = [
        ('git_data', '0010_tag_model_user_tags_m2m'),
    ]

    operations = [
        migrations.RunPython(migrate_tags_forward, migrate_tags_backward),
    ]

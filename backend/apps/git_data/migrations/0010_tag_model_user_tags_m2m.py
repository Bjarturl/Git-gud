from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('git_data', '0009_add_processed_at_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'git_tag',
                'ordering': ['name'],
            },
        ),
        migrations.RenameField(
            model_name='user',
            old_name='tags',
            new_name='legacy_tags',
        ),
        migrations.AddField(
            model_name='user',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='users', to='git_data.tag'),
        ),
    ]

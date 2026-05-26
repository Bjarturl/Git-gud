from django.core.management.base import BaseCommand

from apps.search.models import Regex
from apps.search.management.commands import seeds


class Command(BaseCommand):
    help = "Seed the regex catalog used by the search app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing regex rows matched by seed name and reset progress when pattern changes",
        )
        parser.add_argument(
            "--clear-progress",
            action="store_true",
            help="Reset last_processed_at to NULL for all active regexes, forcing a full rescan",
        )

    def handle(self, *args, **options):
        if options["clear_progress"]:
            count = Regex.objects.filter(is_active=True).update(last_processed_at=None)
            self.stdout.write(self.style.WARNING(f"Cleared progress for {count} active regexes."))
            return

        created_count = 0
        updated_count = 0
        reset_progress_count = 0

        for item in seeds.ALL_SEEDS:
            defaults = {
                "name": item["name"],
                "regex_pattern": item["regex_pattern"],
                "category": item["category"],
            }

            obj = Regex.objects.filter(name=item["name"]).first()

            if obj is None:
                obj, created = Regex.objects.get_or_create(
                    regex_pattern=item["regex_pattern"],
                    defaults=defaults,
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created: {obj.name}"))
                    continue

                if not obj.name and obj.regex_pattern == item["regex_pattern"]:
                    obj.name = item["name"]
                    obj.category = item["category"]
                    obj.save(update_fields=["name", "category", "updated_at"])
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"Updated: {obj.name}"))
                    continue

            if not options["update"]:
                continue

            changed_fields = []
            reset_progress = False

            if obj.regex_pattern != item["regex_pattern"]:
                obj.regex_pattern = item["regex_pattern"]
                obj.last_processed_at = None
                changed_fields.extend(["regex_pattern", "last_processed_at"])
                reset_progress = True

            if obj.name != item["name"]:
                obj.name = item["name"]
                changed_fields.append("name")

            if obj.category != item["category"]:
                obj.category = item["category"]
                changed_fields.append("category")

            if changed_fields:
                changed_fields.append("updated_at")
                obj.save(update_fields=changed_fields)
                updated_count += 1
                if reset_progress:
                    reset_progress_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"Updated and reset progress: {obj.name}")
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"Updated: {obj.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} regexes, updated {updated_count} regexes, reset progress for {reset_progress_count} regexes."
            )
        )

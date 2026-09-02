from django.core.management.base import BaseCommand

from charges.models import BrokerPlan


class Command(BaseCommand):
    help = "Load the broker charge plans that ship with the calculation engine."

    def handle(self, *args, **options):
        created = BrokerPlan.seed()
        total = BrokerPlan.objects.filter(is_system=True).count()
        self.stdout.write(self.style.SUCCESS(f"Seeded {total} plan rows ({created} new)."))

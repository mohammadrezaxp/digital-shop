from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Health check command for Docker and load balancers"

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
            self.stdout.write(
                self.style.SUCCESS("Health check passed: Database is reachable.")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Health check failed: {e}"))
            exit(1)

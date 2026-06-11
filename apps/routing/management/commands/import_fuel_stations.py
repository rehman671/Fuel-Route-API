import pandas as pd
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.routing.models import FuelStation

CSV_PATH = Path(__file__).resolve().parents[2] / "fuel_prices.csv"


class Command(BaseCommand):
    help = "Import fuel stations from CSV into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip import if stations already exist in the DB.",
        )

    def handle(self, *args, **options):
        if options["skip_existing"] and FuelStation.objects.exists():
            self.stdout.write(self.style.WARNING(
                "Stations already in DB and --skip-existing passed. Nothing to do."
            ))
            return

        self.stdout.write("Reading CSV...")
        df = pd.read_csv(CSV_PATH)
        df.columns = [c.strip() for c in df.columns]
        df = df.drop_duplicates(subset=["OPIS Truckstop ID", "Retail Price"])
        self.stdout.write(f"  {len(df)} unique station/price rows loaded.")

        deleted, _ = FuelStation.objects.all().delete()
        if deleted:
            self.stdout.write(f"Cleared {deleted} existing station records.")

        self.stdout.write("Inserting stations into database...")
        stations = [
            FuelStation(
                opis_id      = int(row["OPIS Truckstop ID"]),
                name         = str(row["Truckstop Name"]).strip(),
                address      = str(row["Address"]).strip(),
                city         = str(row["City"]).strip(),
                state        = str(row["State"]).strip(),
                rack_id      = int(row["Rack ID"]),
                retail_price = float(row["Retail Price"]),
            )
            for _, row in df.iterrows()
        ]

        BATCH = 500
        for i in range(0, len(stations), BATCH):
            FuelStation.objects.bulk_create(stations[i : i + BATCH])

        self.stdout.write(self.style.SUCCESS(
            f"Done! {FuelStation.objects.count()} stations imported."
        ))

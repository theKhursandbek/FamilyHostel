"""Add ``location_code`` (controlled enum) and ``location_label`` to Branch.

Telegram Mini App plan §4.2 / D14: catalogue filter relies on a controlled
enum, free-text street/building moves to ``location_label``.
"""

from django.db import migrations, models


LOCATION_KEYWORDS = (
    ("chilanzar", "chilanzar"),
    ("yunusabad", "yunusabad"),
    ("mirzo", "mirzo_ulugbek"),
    ("ulugbek", "mirzo_ulugbek"),
    ("sergeli", "sergeli"),
    ("shayhantahur", "shayhantahur"),
    ("shayxontoxur", "shayhantahur"),
    ("yashnabad", "yashnabad"),
    ("mirobod", "mirobod"),
    ("uchtepa", "uchtepa"),
    ("bektemir", "bektemir"),
    ("olmazar", "olmazar"),
    ("yakkasaray", "yakkasaray"),
    ("samarqand", "samarqand"),
    ("samarkand", "samarqand"),
)


def backfill_location_code(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.all():
        text = (branch.location or "").strip()
        lower = text.lower()
        code = "other"
        for needle, value in LOCATION_KEYWORDS:
            if needle in lower:
                code = value
                break
        branch.location_code = code
        branch.location_label = text[:128]
        branch.save(update_fields=["location_code", "location_label"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0007_strip_brand_prefix"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="location_code",
            field=models.CharField(
                choices=[
                    ("chilanzar", "Chilanzar"),
                    ("yunusabad", "Yunusabad"),
                    ("mirzo_ulugbek", "Mirzo Ulug'bek"),
                    ("sergeli", "Sergeli"),
                    ("shayhantahur", "Shayhantahur"),
                    ("yashnabad", "Yashnabad"),
                    ("mirobod", "Mirobod"),
                    ("uchtepa", "Uchtepa"),
                    ("bektemir", "Bektemir"),
                    ("olmazar", "Olmazar"),
                    ("yakkasaray", "Yakkasaray"),
                    ("samarqand", "Samarqand"),
                    ("other", "Other"),
                ],
                db_index=True,
                default="other",
                help_text="Controlled enum used by the public catalogue location filter.",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="location_label",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Free-text street / building shown next to the location pill.",
                max_length=128,
            ),
        ),
        migrations.RunPython(backfill_location_code, noop_reverse),
    ]

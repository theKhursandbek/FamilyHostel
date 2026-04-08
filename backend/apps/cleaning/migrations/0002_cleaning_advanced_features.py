# Generated manually for Step 21.1 — Cleaning advanced features.
#
# Changes:
#   CleaningTask:
#     - Add retry_count (PositiveIntegerField, default=0)
#     - Add override_reason (TextField, blank/default="")
#     - Add overridden_by (FK → accounts.Account, nullable)
#     - Expand status choices to include retry_required
#     - Update UniqueConstraint to exclude retry_required
#
#   CleaningImage:
#     - Remove image_url (URLField)
#     - Add image (ImageField)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cleaning", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── CleaningTask: new fields ──
        migrations.AddField(
            model_name="cleaningtask",
            name="retry_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cleaningtask",
            name="override_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="cleaningtask",
            name="overridden_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="overridden_tasks",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # ── CleaningTask: update status choices ──
        migrations.AlterField(
            model_name="cleaningtask",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("in_progress", "In Progress"),
                    ("completed", "Completed"),
                    ("retry_required", "Retry Required"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        # ── CleaningTask: update constraint to also exclude retry_required ──
        migrations.RemoveConstraint(
            model_name="cleaningtask",
            name="unique_active_cleaning_task_per_room",
        ),
        migrations.AddConstraint(
            model_name="cleaningtask",
            constraint=models.UniqueConstraint(
                condition=~models.Q(
                    status__in=["completed", "retry_required"],
                ),
                fields=("room",),
                name="unique_active_cleaning_task_per_room",
            ),
        ),
        # ── CleaningImage: replace image_url with ImageField ──
        migrations.RemoveField(
            model_name="cleaningimage",
            name="image_url",
        ),
        migrations.AddField(
            model_name="cleaningimage",
            name="image",
            field=models.ImageField(
                upload_to="cleaning_images/%Y/%m/%d/",
                default="",
            ),
            preserve_default=False,
        ),
    ]

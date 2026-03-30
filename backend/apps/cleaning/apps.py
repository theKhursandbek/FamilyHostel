from django.apps import AppConfig


class CleaningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cleaning"
    verbose_name = "Cleaning System"

    def ready(self):
        import apps.cleaning.signals  # noqa: F401

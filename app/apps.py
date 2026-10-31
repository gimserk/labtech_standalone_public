from django.apps import AppConfig

class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        import app.signals
        import app.checks  # noqa: F401
        import app.student_activity_signals  # noqa: F401
        import app.student_activity_detail_signals  # noqa: F401

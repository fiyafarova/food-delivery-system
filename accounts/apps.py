from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
    # Migration 0002 switched ids to AutoField; keep it so no new migration is needed.
    default_auto_field = 'django.db.models.AutoField'

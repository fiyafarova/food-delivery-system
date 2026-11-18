from django.apps import AppConfig


class RestaurantsConfig(AppConfig):
    name = 'restaurants'
    # Migration 0002 switched ids to AutoField; keep it so no new migration is needed.
    default_auto_field = 'django.db.models.AutoField'

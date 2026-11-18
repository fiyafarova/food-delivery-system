"""Create the group "Restaurant staff" so every database has it after `migrate`."""

from django.db import migrations

STAFF_GROUP = "Restaurant staff"  # same value as staff.permissions.STAFF_GROUP


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=STAFF_GROUP)


def delete_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=STAFF_GROUP).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_group, delete_group),
    ]

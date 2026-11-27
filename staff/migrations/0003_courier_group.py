"""Create the group "Courier" so every database has it after `migrate`."""

from django.db import migrations

COURIER_GROUP = "Courier"  # same value as staff.permissions.COURIER_GROUP


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=COURIER_GROUP)


def delete_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=COURIER_GROUP).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0002_temporary_password'),
    ]

    operations = [
        migrations.RunPython(create_group, delete_group),
    ]

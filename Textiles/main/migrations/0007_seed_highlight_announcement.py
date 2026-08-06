from django.db import migrations

HIGHLIGHT_TEXT = 'FLAT 10% OFF on your first order – Use Code: NIYA10'


def seed(apps, schema_editor):
    Announcement = apps.get_model('main', 'Announcement')
    Announcement.objects.get_or_create(
        text=HIGHLIGHT_TEXT,
        defaults={'icon': '✨', 'order': 10, 'is_active': True, 'is_highlight': True},
    )


def unseed(apps, schema_editor):
    Announcement = apps.get_model('main', 'Announcement')
    Announcement.objects.filter(text=HIGHLIGHT_TEXT).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_remove_product_color_announcement_is_highlight_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

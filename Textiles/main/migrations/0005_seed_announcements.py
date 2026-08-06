from django.db import migrations

ANNOUNCEMENTS = [
    ('🚚', 'FREE SHIPPING on orders above ₹1999', 0),
    ('📦', 'COD Available', 1),
    ('↩️', 'Easy 7-Day Returns', 2),
]


def seed(apps, schema_editor):
    Announcement = apps.get_model('main', 'Announcement')
    for icon, text, order in ANNOUNCEMENTS:
        Announcement.objects.get_or_create(text=text, defaults={'icon': icon, 'order': order, 'is_active': True})


def unseed(apps, schema_editor):
    Announcement = apps.get_model('main', 'Announcement')
    Announcement.objects.filter(text__in=[a[1] for a in ANNOUNCEMENTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_announcement_section_show_in_home'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

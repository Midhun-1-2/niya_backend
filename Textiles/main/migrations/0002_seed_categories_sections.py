from django.db import migrations

CATEGORIES = [
    ('Kanjivaram', 'kanjivaram', 0),
    ('Banarasi', 'banarasi', 1),
    ('Patola', 'patola', 2),
    ('Organza', 'organza', 3),
    ('Party Wear', 'party-wear', 4),
    ('Cotton', 'cotton', 5),
]

SECTIONS = [
    ('Bestsellers', 'bestsellers', 0, False),
    ('New Arrivals', 'new-arrivals', 1, False),
    ('Sale', 'sale', 2, True),
]


def seed(apps, schema_editor):
    Category = apps.get_model('main', 'Category')
    Section = apps.get_model('main', 'Section')

    for name, slug, order in CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={'name': name, 'order': order, 'is_active': True})

    for name, slug, order, is_sale in SECTIONS:
        Section.objects.get_or_create(
            slug=slug, defaults={'name': name, 'order': order, 'is_active': True, 'is_sale': is_sale}
        )


def unseed(apps, schema_editor):
    Category = apps.get_model('main', 'Category')
    Section = apps.get_model('main', 'Section')
    Category.objects.filter(slug__in=[c[1] for c in CATEGORIES]).delete()
    Section.objects.filter(slug__in=[s[1] for s in SECTIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

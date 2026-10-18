from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model('wardrobe', 'Category')
    default_categories = [
        {'name': 'Tops', 'slug': 'tops', 'display_order': 1},
        {'name': 'Bottoms', 'slug': 'bottoms', 'display_order': 2},
        {'name': 'Footwear', 'slug': 'footwear', 'display_order': 3},
        {'name': 'Outerwear', 'slug': 'outerwear', 'display_order': 4},
        {'name': 'Accessories', 'slug': 'accessories', 'display_order': 5},
        {'name': 'Dresses & Jumpsuits', 'slug': 'dresses', 'display_order': 6},
    ]
    for cat_data in default_categories:
        Category.objects.get_or_create(slug=cat_data['slug'], defaults=cat_data)


def rollback_categories(apps, schema_editor):
    Category = apps.get_model('wardrobe', 'Category')
    Category.objects.filter(slug__in=['tops', 'bottoms', 'footwear', 'outerwear', 'accessories', 'dresses']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('wardrobe', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=rollback_categories),
    ]

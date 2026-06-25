from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0008_inventorysession_archive"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.CharField(blank=True, default="slate", max_length=32),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0007_movement_writeoff_archive"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorysession",
            name="archived",
            field=models.BooleanField(default=False),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="archived_by_requester",
            field=models.BooleanField(default=False),
        ),
    ]

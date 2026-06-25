from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_alter_servicerequest_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="movement",
            name="archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="archived",
            field=models.BooleanField(default=False),
        ),
    ]

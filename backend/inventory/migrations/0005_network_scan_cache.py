from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_network_infrastructure"),
    ]

    operations = [
        migrations.AddField(
            model_name="networkipaddress",
            name="last_scanned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="networkipaddress",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="networkipaddress",
            name="scan_source",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]

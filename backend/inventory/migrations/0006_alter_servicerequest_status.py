from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_network_scan_cache"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicerequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("review", "На рассмотрении"),
                    ("approved", "В работе"),
                    ("rejected", "Отклонено"),
                    ("done", "Выполнено"),
                ],
                default="review",
                max_length=32,
            ),
        ),
    ]

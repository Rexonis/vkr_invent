from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_service_request_archive"),
    ]

    operations = [
        migrations.CreateModel(
            name="InfrastructureSegment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(blank=True, max_length=80)),
                ("owner", models.CharField(blank=True, max_length=160)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="InternetLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=180)),
                ("contract_number", models.CharField(blank=True, max_length=120)),
                ("speed_mbps", models.PositiveIntegerField(default=0)),
                ("external_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(default="Активен", max_length=80)),
                ("contacts", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["provider", "location"]},
        ),
        migrations.CreateModel(
            name="NetworkDomain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("registrar", models.CharField(blank=True, max_length=180)),
                ("dns_servers", models.TextField(blank=True)),
                ("owner", models.CharField(blank=True, max_length=160)),
                ("expires_at", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="TelephonyLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=180)),
                ("number", models.CharField(max_length=80)),
                ("line_type", models.CharField(blank=True, max_length=120)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("employee", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(default="Активна", max_length=80)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["number"]},
        ),
        migrations.CreateModel(
            name="Network",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("cidr", models.CharField(max_length=64)),
                ("gateway", models.GenericIPAddressField(blank=True, null=True)),
                ("purpose", models.CharField(blank=True, max_length=220)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("segment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.infrastructuresegment")),
            ],
            options={"ordering": ["cidr", "name"]},
        ),
        migrations.CreateModel(
            name="NetworkVlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vlan_id", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=160)),
                ("purpose", models.CharField(blank=True, max_length=220)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("network", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.network")),
                ("segment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.infrastructuresegment")),
            ],
            options={"ordering": ["vlan_id", "name"]},
        ),
        migrations.CreateModel(
            name="NetworkIpAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address", models.GenericIPAddressField()),
                ("hostname", models.CharField(blank=True, max_length=180)),
                ("owner", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("free", "Свободен"), ("reserved", "Зарезервирован"), ("used", "Используется")], default="used", max_length=32)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("network", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.network")),
                ("vlan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="inventory.networkvlan")),
            ],
            options={"ordering": ["address"]},
        ),
    ]

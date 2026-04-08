"""
employees/migrations/0001_initial.py
Auto-generated initial migration for the employees app.
"""
import decimal
import django.db.models.deletion
import django.utils.timezone
import employees.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("inventory", "0004_producttag_productserialnumber_stockalert_and_more"),
        ("sales", "0006_saleitem_custom_item_name_saleitem_item_note"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── EmployeeProfile ────────────────────────────────────────────────
        migrations.CreateModel(
            name="EmployeeProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(default=employees.models._next_employee_id, help_text="Auto-generated, e.g. EMP-001", max_length=20, unique=True)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("national_id", models.CharField(blank=True, max_length=50)),
                ("address", models.TextField(blank=True)),
                ("date_hired", models.DateField()),
                ("date_terminated", models.DateField(blank=True, null=True)),
                ("employment_type", models.CharField(choices=[("full_time", "Full-Time"), ("part_time", "Part-Time"), ("contract", "Contract"), ("intern", "Intern")], default="full_time", max_length=20)),
                ("department", models.CharField(choices=[("sales", "Sales"), ("management", "Management"), ("operations", "Operations"), ("admin", "Admin")], default="sales", max_length=20)),
                ("emergency_contact_name", models.CharField(blank=True, max_length=200)),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=30)),
                ("profile_photo", models.ImageField(blank=True, null=True, upload_to="employees/photos/")),
                ("bank_name", models.CharField(blank=True, max_length=100)),
                ("bank_account", models.CharField(blank=True, max_length=50)),
                ("commission_rate_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), help_text="Commission % applied to sales (0 = no commission)", max_digits=5)),
                ("notes", models.TextField(blank=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="employee_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["user__first_name", "user__last_name"], "verbose_name": "Employee Profile"},
        ),

        # ── Shift ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Shift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_confirmed", models.BooleanField(default=False)),
                ("notes", models.CharField(blank=True, max_length=300)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="shifts_confirmed", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shifts", to=settings.AUTH_USER_MODEL)),
                ("joint", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shifts", to="inventory.joint")),
            ],
            options={"ordering": ["-date", "start_time"], "verbose_name": "Shift"},
        ),
        migrations.AlterUniqueTogether(
            name="shift",
            unique_together={("employee", "date")},
        ),

        # ── Attendance ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Attendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clock_in", models.DateTimeField()),
                ("clock_out", models.DateTimeField(blank=True, null=True)),
                ("total_hours", models.DecimalField(blank=True, decimal_places=2, help_text="Computed on clock-out", max_digits=5, null=True)),
                ("is_late", models.BooleanField(default=False)),
                ("notes", models.CharField(blank=True, max_length=300)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to=settings.AUTH_USER_MODEL)),
                ("joint", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to="inventory.joint")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_recorded", to=settings.AUTH_USER_MODEL)),
                ("shift", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance", to="employees.shift")),
            ],
            options={"ordering": ["-clock_in"], "verbose_name": "Attendance Record"},
        ),

        # ── LeaveRequest ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("leave_type", models.CharField(choices=[("annual", "Annual Leave"), ("sick", "Sick Leave"), ("emergency", "Emergency Leave"), ("unpaid", "Unpaid Leave"), ("maternity", "Maternity Leave")], max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("days_requested", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="leave_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Leave Request"},
        ),

        # ── PerformanceReview ─────────────────────────────────────────────
        migrations.CreateModel(
            name="PerformanceReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_period_start", models.DateField()),
                ("review_period_end", models.DateField()),
                ("sales_score", models.PositiveSmallIntegerField(default=3)),
                ("attendance_score", models.PositiveSmallIntegerField(default=3)),
                ("attitude_score", models.PositiveSmallIntegerField(default=3)),
                ("overall_score", models.DecimalField(decimal_places=2, default=decimal.Decimal("3.00"), max_digits=3)),
                ("strengths", models.TextField(blank=True)),
                ("improvements", models.TextField(blank=True)),
                ("goals", models.TextField(blank=True)),
                ("is_shared", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_reviews", to=settings.AUTH_USER_MODEL)),
                ("reviewer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews_given", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-review_period_end"], "verbose_name": "Performance Review"},
        ),

        # ── Commission ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Commission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rate_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("period", models.DateField(help_text="Month/year of commission (first of month)")),
                ("is_paid", models.BooleanField(default=False)),
                ("paid_at", models.DateField(blank=True, null=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commissions", to=settings.AUTH_USER_MODEL)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commissions", to="sales.sale")),
            ],
            options={"ordering": ["-period", "employee"], "verbose_name": "Commission"},
        ),
    ]

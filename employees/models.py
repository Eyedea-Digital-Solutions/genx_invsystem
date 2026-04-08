"""
employees/models.py
────────────────────
Section 5 — Employee Management Module

Models:
  EmployeeProfile  — OneToOne with User, full HR data
  Shift            — Scheduled work periods per joint
  Attendance       — Clock-in / clock-out records
  LeaveRequest     — Annual, sick, emergency, unpaid, maternity
  PerformanceReview — Scored reviews with sharing controls
  Commission       — Per-sale commission tracking
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


# ── auto-generate employee ID ─────────────────────────────────────────────────

def _next_employee_id():
    last = EmployeeProfile.objects.order_by("-id").first()
    if last and last.employee_id:
        try:
            n = int(last.employee_id.split("-")[1]) + 1
        except (IndexError, ValueError):
            n = 1
    else:
        n = 1
    return f"EMP-{str(n).zfill(3)}"


# ═════════════════════════════════════════════════════════════════════════════
class EmployeeProfile(models.Model):
    """Extended HR profile — OneToOne with the custom User model."""

    EMPLOYMENT_FULL_TIME = "full_time"
    EMPLOYMENT_PART_TIME = "part_time"
    EMPLOYMENT_CONTRACT  = "contract"
    EMPLOYMENT_INTERN    = "intern"

    EMPLOYMENT_CHOICES = [
        (EMPLOYMENT_FULL_TIME, "Full-Time"),
        (EMPLOYMENT_PART_TIME, "Part-Time"),
        (EMPLOYMENT_CONTRACT,  "Contract"),
        (EMPLOYMENT_INTERN,    "Intern"),
    ]

    DEPT_SALES       = "sales"
    DEPT_MANAGEMENT  = "management"
    DEPT_OPERATIONS  = "operations"
    DEPT_ADMIN       = "admin"

    DEPARTMENT_CHOICES = [
        (DEPT_SALES,      "Sales"),
        (DEPT_MANAGEMENT, "Management"),
        (DEPT_OPERATIONS, "Operations"),
        (DEPT_ADMIN,      "Admin"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_id = models.CharField(
        max_length=20, unique=True, default=_next_employee_id,
        help_text="Auto-generated, e.g. EMP-001",
    )

    # ── Personal ──────────────────────────────────────────────────────────────
    date_of_birth = models.DateField(null=True, blank=True)
    national_id   = models.CharField(max_length=50, blank=True)
    address       = models.TextField(blank=True)

    # ── Employment ────────────────────────────────────────────────────────────
    date_hired      = models.DateField()
    date_terminated = models.DateField(null=True, blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EMPLOYMENT_CHOICES, default=EMPLOYMENT_FULL_TIME
    )
    department = models.CharField(
        max_length=20, choices=DEPARTMENT_CHOICES, default=DEPT_SALES
    )

    # ── Emergency contact ────────────────────────────────────────────────────
    emergency_contact_name  = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)

    # ── Media ─────────────────────────────────────────────────────────────────
    profile_photo = models.ImageField(
        upload_to="employees/photos/", null=True, blank=True
    )

    # ── Banking ───────────────────────────────────────────────────────────────
    bank_name    = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)

    # ── Commission rate (used by Commission model) ────────────────────────────
    commission_rate_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        help_text="Commission % applied to sales (0 = no commission)",
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering     = ["user__first_name", "user__last_name"]
        verbose_name = "Employee Profile"

    def __str__(self):
        return f"{self.employee_id} — {self.user.get_full_name() or self.user.username}"

    @property
    def is_active_employee(self):
        return self.date_terminated is None

    @property
    def days_employed(self):
        end = self.date_terminated or timezone.now().date()
        return (end - self.date_hired).days

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


# ═════════════════════════════════════════════════════════════════════════════
class Shift(models.Model):
    """Scheduled shift — one record per employee per day."""

    employee      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shifts"
    )
    joint         = models.ForeignKey(
        "inventory.Joint", on_delete=models.CASCADE, related_name="shifts"
    )
    date          = models.DateField()
    start_time    = models.TimeField()
    end_time      = models.TimeField()
    is_confirmed  = models.BooleanField(default=False)
    confirmed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="shifts_confirmed",
    )
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering     = ["-date", "start_time"]
        verbose_name = "Shift"
        unique_together = [["employee", "date"]]

    def __str__(self):
        return (
            f"{self.employee.get_full_name() or self.employee.username} — "
            f"{self.date} {self.start_time}–{self.end_time} @ {self.joint.display_name}"
        )

    @property
    def duration_hours(self):
        from datetime import datetime, date as dt
        s = datetime.combine(dt.today(), self.start_time)
        e = datetime.combine(dt.today(), self.end_time)
        diff = (e - s).total_seconds() / 3600
        return round(diff, 2) if diff > 0 else round(diff + 24, 2)


# ═════════════════════════════════════════════════════════════════════════════
class Attendance(models.Model):
    """Clock-in / clock-out record — may or may not be tied to a Shift."""

    employee    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    shift       = models.ForeignKey(
        Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance"
    )
    joint       = models.ForeignKey(
        "inventory.Joint", on_delete=models.CASCADE, related_name="attendance_records"
    )
    clock_in    = models.DateTimeField()
    clock_out   = models.DateTimeField(null=True, blank=True)
    total_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Computed on clock-out",
    )
    is_late     = models.BooleanField(
        default=False,
        help_text="True when clock_in > shift.start_time + 15 min",
    )
    notes       = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_recorded",
    )

    class Meta:
        ordering     = ["-clock_in"]
        verbose_name = "Attendance Record"

    def __str__(self):
        name = self.employee.get_full_name() or self.employee.username
        return f"{name} — {self.clock_in.strftime('%d %b %Y %H:%M')}"

    def clock_out_now(self, actor=None):
        """Set clock_out, compute total_hours, flag lateness."""
        self.clock_out = timezone.now()
        delta = (self.clock_out - self.clock_in).total_seconds() / 3600
        self.total_hours = Decimal(str(round(delta, 2)))
        self.save(update_fields=["clock_out", "total_hours"])

    def compute_lateness(self):
        """Populate is_late against linked shift (15-min grace period)."""
        if not self.shift:
            return
        from datetime import datetime, timedelta
        grace = datetime.combine(self.clock_in.date(), self.shift.start_time)
        grace = timezone.make_aware(grace) + timedelta(minutes=15)
        self.is_late = self.clock_in > grace
        self.save(update_fields=["is_late"])


# ═════════════════════════════════════════════════════════════════════════════
class LeaveRequest(models.Model):
    """Employee leave application with manager approval workflow."""

    TYPE_ANNUAL    = "annual"
    TYPE_SICK      = "sick"
    TYPE_EMERGENCY = "emergency"
    TYPE_UNPAID    = "unpaid"
    TYPE_MATERNITY = "maternity"

    LEAVE_TYPE_CHOICES = [
        (TYPE_ANNUAL,    "Annual Leave"),
        (TYPE_SICK,      "Sick Leave"),
        (TYPE_EMERGENCY, "Emergency Leave"),
        (TYPE_UNPAID,    "Unpaid Leave"),
        (TYPE_MATERNITY, "Maternity Leave"),
    ]

    STATUS_PENDING  = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date   = models.DateField()
    reason     = models.TextField()
    status     = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    reviewed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_reviews",
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    days_requested = models.PositiveIntegerField(
        help_text="Computed from start_date / end_date", default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["-created_at"]
        verbose_name = "Leave Request"

    def __str__(self):
        name = self.employee.get_full_name() or self.employee.username
        return f"{name} — {self.get_leave_type_display()} ({self.start_date} → {self.end_date})"

    def save(self, *args, **kwargs):
        # Auto-compute days_requested
        if self.start_date and self.end_date:
            self.days_requested = max(1, (self.end_date - self.start_date).days + 1)
        super().save(*args, **kwargs)

    def approve(self, reviewer):
        self.status      = self.STATUS_APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    def reject(self, reviewer):
        self.status      = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])


# ═════════════════════════════════════════════════════════════════════════════
class PerformanceReview(models.Model):
    """Scored review with optional sharing so the employee can view it."""

    employee  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="performance_reviews"
    )
    reviewer  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_given"
    )
    review_period_start = models.DateField()
    review_period_end   = models.DateField()

    # ── Scores 1–5 ──────────────────────────────────────────────────────────
    sales_score      = models.PositiveSmallIntegerField(default=3, help_text="1–5")
    attendance_score = models.PositiveSmallIntegerField(default=3, help_text="1–5")
    attitude_score   = models.PositiveSmallIntegerField(default=3, help_text="1–5")
    overall_score    = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("3.00"),
        help_text="Computed average",
    )

    # ── Narrative ─────────────────────────────────────────────────────────────
    strengths    = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    goals        = models.TextField(blank=True)

    is_shared  = models.BooleanField(
        default=False, help_text="Employee can view once shared"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["-review_period_end"]
        verbose_name = "Performance Review"

    def __str__(self):
        name = self.employee.get_full_name() or self.employee.username
        return f"{name} — {self.review_period_start} → {self.review_period_end}"

    def save(self, *args, **kwargs):
        # Recompute overall score as average of three dimensions
        total = self.sales_score + self.attendance_score + self.attitude_score
        self.overall_score = Decimal(str(round(total / 3, 2)))
        super().save(*args, **kwargs)

    def share(self):
        self.is_shared = True
        self.save(update_fields=["is_shared"])

    @property
    def score_label(self):
        s = float(self.overall_score)
        if s >= 4.5: return "Outstanding"
        if s >= 3.5: return "Exceeds Expectations"
        if s >= 2.5: return "Meets Expectations"
        if s >= 1.5: return "Needs Improvement"
        return "Unsatisfactory"

    @property
    def score_color(self):
        s = float(self.overall_score)
        if s >= 4.0: return "green"
        if s >= 3.0: return "blue"
        if s >= 2.0: return "amber"
        return "red"


# ═════════════════════════════════════════════════════════════════════════════
class Commission(models.Model):
    """Per-sale commission record — populated when a POS sale is completed."""

    employee      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="commissions"
    )
    sale          = models.ForeignKey(
        "sales.Sale", on_delete=models.CASCADE, related_name="commissions"
    )
    rate_percent  = models.DecimalField(max_digits=5, decimal_places=2)
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    period        = models.DateField(help_text="Month/year of commission (first of month)")
    is_paid       = models.BooleanField(default=False)
    paid_at       = models.DateField(null=True, blank=True)

    class Meta:
        ordering     = ["-period", "employee"]
        verbose_name = "Commission"

    def __str__(self):
        name = self.employee.get_full_name() or self.employee.username
        return f"{name} — ${self.amount} @ {self.rate_percent}% [{self.period.strftime('%b %Y')}]"

    @classmethod
    def create_for_sale(cls, sale):
        """
        Auto-create a Commission record when a sale is completed,
        if the cashier has commission_rate_percent > 0.
        Called from pos_complete signal / post_save.
        """
        if not sale.sold_by:
            return None
        try:
            profile = sale.sold_by.employee_profile
        except cls.DoesNotExist:
            return None

        rate = profile.commission_rate_percent
        if rate <= 0:
            return None

        amount = (sale.total_amount * rate / 100).quantize(Decimal("0.01"))
        period = sale.sale_date.date().replace(day=1)

        return cls.objects.create(
            employee=sale.sold_by,
            sale=sale,
            rate_percent=rate,
            amount=amount,
            period=period,
        )

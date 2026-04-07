"""
employees/forms.py
All forms for the Employee Management module.
"""
from django import forms
from django.utils import timezone
from .models import EmployeeProfile, Shift, Attendance, LeaveRequest, PerformanceReview


_W = lambda cls, **kw: {"class": cls, **kw}


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model  = EmployeeProfile
        exclude = ["user", "employee_id"]
        widgets = {
            "date_of_birth":           forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "date_hired":              forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "date_terminated":         forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "employment_type":         forms.Select(attrs={"class": "form-select"}),
            "department":              forms.Select(attrs={"class": "form-select"}),
            "national_id":             forms.TextInput(attrs={"class": "form-control"}),
            "address":                 forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "emergency_contact_name":  forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "bank_name":               forms.TextInput(attrs={"class": "form-control"}),
            "bank_account":            forms.TextInput(attrs={"class": "form-control"}),
            "commission_rate_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}),
            "profile_photo":           forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "notes":                   forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ShiftForm(forms.ModelForm):
    class Meta:
        model  = Shift
        fields = ["employee", "joint", "date", "start_time", "end_time", "notes"]
        widgets = {
            "employee":   forms.Select(attrs={"class": "form-select"}),
            "joint":      forms.Select(attrs={"class": "form-select"}),
            "date":       forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "end_time":   forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "notes":      forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional notes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from users.models import User
        self.fields["employee"].queryset = User.objects.filter(is_active=True).order_by("first_name")


class AttendanceClockInForm(forms.ModelForm):
    class Meta:
        model  = Attendance
        fields = ["employee", "joint", "shift", "notes"]
        widgets = {
            "employee": forms.Select(attrs={"class": "form-select"}),
            "joint":    forms.Select(attrs={"class": "form-select"}),
            "shift":    forms.Select(attrs={"class": "form-select"}),
            "notes":    forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from users.models import User
        today = timezone.localdate()
        self.fields["employee"].queryset = User.objects.filter(is_active=True).order_by("first_name")
        self.fields["shift"].queryset    = Shift.objects.filter(date=today)
        self.fields["shift"].required    = False


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model  = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "leave_type": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date":   forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "reason":     forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Reason for leave…"}),
        }

    def clean(self):
        cd = super().clean()
        s, e = cd.get("start_date"), cd.get("end_date")
        if s and e and e < s:
            raise forms.ValidationError("End date must be on or after start date.")
        return cd


class LeaveReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=[("approve", "Approve"), ("reject", "Reject")],
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )


class PerformanceReviewForm(forms.ModelForm):
    SCORE_CHOICES = [(i, str(i)) for i in range(1, 6)]

    sales_score      = forms.ChoiceField(choices=SCORE_CHOICES, widget=forms.RadioSelect)
    attendance_score = forms.ChoiceField(choices=SCORE_CHOICES, widget=forms.RadioSelect)
    attitude_score   = forms.ChoiceField(choices=SCORE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model  = PerformanceReview
        fields = [
            "employee", "review_period_start", "review_period_end",
            "sales_score", "attendance_score", "attitude_score",
            "strengths", "improvements", "goals", "is_shared",
        ]
        widgets = {
            "employee":            forms.Select(attrs={"class": "form-select"}),
            "review_period_start": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "review_period_end":   forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "strengths":           forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "improvements":        forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "goals":               forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_shared":           forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from users.models import User
        self.fields["employee"].queryset = User.objects.filter(is_active=True).order_by("first_name")

    def clean_sales_score(self):
        return int(self.cleaned_data["sales_score"])

    def clean_attendance_score(self):
        return int(self.cleaned_data["attendance_score"])

    def clean_attitude_score(self):
        return int(self.cleaned_data["attitude_score"])


class EmployeeFilterForm(forms.Form):
    from inventory.models import Joint
    joint = forms.ModelChoiceField(
        queryset=Joint.objects.all(),
        required=False, empty_label="All Joints",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    department = forms.ChoiceField(
        required=False,
        choices=[("", "All Departments")] + EmployeeProfile.DEPARTMENT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    employment_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + EmployeeProfile.EMPLOYMENT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-sm",
            "placeholder": "Search name or ID…",
        }),
    )
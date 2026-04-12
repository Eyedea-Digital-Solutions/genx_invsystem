# ============================================================
# GENX POS v5 — BUG FIXES REFERENCE
# Apply these patches to the relevant existing files.
# ============================================================

# ── FIX 1: inventory/models.py ──────────────────────────────
# StockTakeItem has BOTH a `variance` database field AND a `variance` property.
# Remove the property — the field takes precedence and the property shadows it,
# causing AttributeError on save. Delete or rename the property:
#
# BEFORE (in StockTakeItem):
#   variance = models.IntegerField(default=0)  # db field
#   ...
#   @property
#   def variance(self):                         # CONFLICT — remove this
#       return self.counted_quantity - self.expected_quantity
#
# AFTER — remove the @property entirely; compute variance on save instead:
#   def save(self, *args, **kwargs):
#       self.variance = (self.counted_quantity or 0) - (self.expected_quantity or 0)
#       super().save(*args, **kwargs)

# ── FIX 2: inventory/urls.py ────────────────────────────────
# Duplicate path name 'stock_take_list'. Remove one:
#
# BEFORE:
#   path('stock-take/', views.stock_take_list, name='stock_take_list'),
#   path('stock-take/list/', views.stock_take_list, name='stock_take_list'),  # ← REMOVE
#
# AFTER:
#   path('stock-take/', views.stock_take_list, name='stock_take_list'),

# ── FIX 3: inventory/views_v4.py ────────────────────────────
# StockTake.objects.order_by('-created_at') — model uses conducted_at, not created_at.
#
# BEFORE:
#   StockTake.objects.order_by('-created_at')
#
# AFTER:
#   StockTake.objects.order_by('-conducted_at')

# ── FIX 4: returns/views.py ─────────────────────────────────
# Uses __import__ hack for Sum. Replace with proper import:
#
# BEFORE (top of file or inside function):
#   Sum = __import__('django.db.models', fromlist=['Sum']).Sum
#
# AFTER (at top of file with other imports):
#   from django.db.models import Sum

# ── FIX 5: sales/analytics_views.py ────────────────────────
# Min imported at bottom but used in functions. Move to top of file:
#
# BEFORE (somewhere mid-file or bottom):
#   from django.db.models import Min
#
# AFTER (at top with other imports):
#   from django.db.models import Avg, Count, Max, Min, Sum

# ── FIX 6: employees app not in INSTALLED_APPS ──────────────
# See settings_patch.py — add 'employees' to INSTALLED_APPS
# and run: python manage.py migrate employees

# Multi-Joint POS & Inventory System
### Eyedentity · GenX Zimbabwe · Armor Sole

A full-stack Django system for managing sales, stock, and reporting across all 3 of your joints.

---

## Features

- ✅ **3 Joint Management** — Eyedentity, GenX, Armor Sole on one system
- ✅ **Product Codes** — Eyedentity and Armor Sole support product codes
- ✅ **Auto Stock Deduction** — Stock automatically drops when a sale is made
- ✅ **System Sales** — Select products, print receipt (GNX-0001, EYE-0001, ARM-0001)
- ✅ **Manual Sales** — Upload photo of manual receipt; system creates a digital record
- ✅ **Low Stock Alerts** — Dashboard highlights anything at 3 units or fewer
- ✅ **EcoCash Payments** — Record EcoCash payment with your Econet number, confirm by entering customer's transaction reference
- ✅ **Sales Cannot Be Undone** — Enforced at the database and code level with an audit trail
- ✅ **Who Made Each Sale** — Every sale records the logged-in staff member
- ✅ **Monthly Stock Takes** — Record physical counts vs system counts, log variances
- ✅ **Stock Transfers** — Move stock between joints
- ✅ **Reports** — Revenue by joint, payment method breakdown, top products, staff performance
- ✅ **Role-Based Access** — Admin / Manager / Staff roles with different permissions
- ✅ **Printable Receipts** — Styled to match your physical receipt books (Eyedentity, GenX, Armor Sole)

---

## Setup Instructions

### Step 1: Install Python (if not installed)
Download Python 3.10+ from https://www.python.org/downloads/

### Step 2: Create a virtual environment
```bash
cd inventory_system
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run database migrations
This creates the database tables.
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Set up the 3 joints (shops)
```bash
python manage.py setup_initial_data
```

### Step 6: Create your admin account
```bash
python manage.py createsuperuser
```
Enter your username, email and password when prompted.

### Step 7: Start the server
```bash
python manage.py runserver
```

Then open your browser at: **http://127.0.0.1:8000**

---

## First-Time Setup (After logging in)

1. **Go to Inventory → Products → Add Product** to add your products
2. **Set stock quantities** using the "+Stock" button on each product
3. **Create staff accounts** at Users → Add User
4. Assign roles:
   - `Admin` — can do everything (you)
   - `Manager` — can view reports, manage stock and products
   - `Staff` — can only make sales

---

## EcoCash Setup

Open `inventory_system/settings.py` and update:

```python
ECOCASH_ECONET_NUMBER = '0777000000'  # ← Replace with YOUR EcoCash number
ECOCASH_MERCHANT_NAME = 'GenX Zimbabwe'
```

### How EcoCash Payments Work:
1. Staff selects "EcoCash" as payment method
2. Sale is saved, system shows: "Send $XX to 0777XXXXXX, reference: GNX-0001"
3. Customer pays and gets an SMS with a transaction code (e.g., MMM123456789)
4. Staff goes to **EcoCash → Pending Payments**, clicks Confirm, enters the code
5. Payment is marked as confirmed ✅

---

## Receipt Numbers

Receipts are auto-numbered per joint:
- **EYE-0001, EYE-0002...** — Eyedentity
- **GNX-0001, GNX-0002...** — GenX
- **ARM-0001, ARM-0002...** — Armor Sole

---

## User Roles

| Feature | Staff | Manager | Admin |
|---------|-------|---------|-------|
| Make sales | ✅ | ✅ | ✅ |
| View own sales | ✅ | ✅ | ✅ |
| View all sales | ❌ | ✅ | ✅ |
| Add/Edit products | ❌ | ✅ | ✅ |
| Adjust stock | ❌ | ✅ | ✅ |
| Stock takes | ❌ | ✅ | ✅ |
| Transfer stock | ❌ | ✅ | ✅ |
| Reports | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| Django admin | ❌ | ❌ | ✅ |

---

## Production Deployment (When Ready)

For production (hosting on a server), you'll want to:
1. Change `SECRET_KEY` in settings.py to a secure random value
2. Set `DEBUG = False`
3. Switch to PostgreSQL database (see settings.py comments)
4. Set up a proper web server (nginx + gunicorn)
5. Set `ALLOWED_HOSTS` to your domain name

---

# genx_invsystem

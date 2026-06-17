# Secure Car Accessories Booking and Management System

A simple, accessible Progressive Web App for **Royal Himalayans**, a Sydney car-accessory installation business.
The system allows customers to browse services, submit installation bookings, and send inquiries, while admins can securely manage bookings through a protected dashboard.

## Run locally

1. Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the Flask server:

```bash
python app.py
```

4. Open the app:

```text
http://127.0.0.1:5000
```

On first run, the database initialises automatically and creates the required tables for services, bookings, admins, and inquiries.

## Structure

* **Backend:** Python Flask, SQLite database, parameterised SQL queries, bcrypt password hashing, input validation, server-side sessions.
* **Frontend:** Jinja2 templates, plain CSS, vanilla JavaScript, responsive black and red interface.
* **Admin system:** Secure admin login, dashboard statistics, booking search, booking status updates, inquiries list, and services view.
* **PWA:** `manifest.json` and service worker support for static asset caching and installable app behaviour.

## Default admin login

* URL: `/admin`
* Username: `admin`
* Password: `admin123`

For security, change the default admin password before deployment.

## Deployment

The project is designed for deployment on Render.

Render start command:

```bash
gunicorn app:app
```

Recommended environment variables:

```bash
SECRET_KEY= #########
ADMIN_PASSWORD= #########
FLASK_ENV=production
```

## Add or edit services

Services are seeded from `database.py` when the database is first created.

To rebuild the database with updated seed data:

1. Edit the service seed data in `database.py`.
2. Delete the local database file:

```text
royal_himalayans.db
```

3. Run the app again:

```bash
python app.py
```

A new database will be created with the updated services.

## Notes

* Services and the default admin account are seeded automatically on first run.
* Booking references are generated in the format `RH-####`.
* SQL queries use placeholders to help prevent SQL injection.
* Admin routes are protected using a `login_required` decorator.
* Admin passwords are stored using bcrypt hashing.
* User input is validated and cleaned before being stored.
* PWA support is included through `static/manifest.json` and `static/js/sw.js`.

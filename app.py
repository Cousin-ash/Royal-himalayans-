"""Main Flask application for the Royal Himalayans PWA.

This file contains:
- public routes such as the homepage, services, booking and contact pages
- admin routes for login, dashboard, bookings, inquiries and services
- validation helpers that clean and check user input before database storage
- security settings such as bcrypt login, server-side sessions and protected admin routes
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_bcrypt import Bcrypt

from database import (
    close_db,
    execute_db,
    generate_booking_ref,
    get_all_services,
    get_service_by_slug,
    init_db,
    query_db,
)


# Admin booking statuses are restricted to these values so users cannot save invalid states.
STATUS_OPTIONS = ("Pending", "Confirmed", "Completed")

# Regular expressions used for simple input cleaning and validation.
TAG_RE = re.compile(r"<[^>]*>")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{8,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Create the Flask application object. Flask uses this object to register routes and settings.
app = Flask(__name__)

# The secret key signs the server-side session cookie. On Render this should come from an environment variable.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-secret-key")

# DATABASE_PATH can be changed on Render/local testing without changing the code.
app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "royal_himalayans.db"))

# Sessions automatically expire after two hours for better admin security.
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)

# Hardened cookie settings help protect login sessions.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production" or os.environ.get("RENDER") == "true"

# Bcrypt is used so admin passwords are never stored as plain text.
bcrypt = Bcrypt(app)

# Create database tables and seed starter data when the application starts.
with app.app_context():
    init_db(bcrypt)

# Close the SQLite connection at the end of each request.
app.teardown_appcontext(close_db)


@app.context_processor
def inject_globals():
    """Make common template values available to every Jinja2 page."""
    return {
        "current_year": datetime.now().year,
        "admin_username": session.get("admin_username"),
    }


def strip_tags(value: str | None, max_length: int = 255) -> str:
    """Remove HTML tags and limit field length before storing user-submitted data."""
    if value is None:
        return ""
    cleaned = TAG_RE.sub("", value).strip()
    return cleaned[:max_length]


def valid_date(value: str) -> bool:
    """Check that a date string is in the expected YYYY-MM-DD format."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def split_features(value: str):
    """Convert a pipe-separated feature string from the database into a list."""
    return [item.strip() for item in value.split("|") if item.strip()]


@app.template_filter("features")
def features_filter(value: str):
    """Jinja2 filter used by templates to display service features as bullet points."""
    return split_features(value or "")


def login_required(view_func):
    """Decorator that blocks admin pages unless the admin is logged in."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please log in to access the admin area.", "error")
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def validate_booking_form(form):
    """Clean and validate booking form data before it is inserted or updated."""
    data = {
        "customer_name": strip_tags(form.get("customer_name"), 80),
        "phone": strip_tags(form.get("phone"), 20),
        "car_model": strip_tags(form.get("car_model"), 80),
        "preferred_date": strip_tags(form.get("preferred_date"), 10),
        "notes": strip_tags(form.get("notes"), 500),
    }
    errors = []

    # Required fields are checked on the server so validation still works if browser checks are bypassed.
    if not data["customer_name"]:
        errors.append("Full name is required.")
    if not data["phone"] or not PHONE_RE.match(data["phone"]):
        errors.append("Enter a valid phone number.")
    if not data["car_model"]:
        errors.append("Car model is required.")
    if not data["preferred_date"] or not valid_date(data["preferred_date"]):
        errors.append("Preferred date is required.")

    return data, errors


def validate_inquiry_form(form):
    """Clean and validate contact inquiry data before database insertion."""
    data = {
        "name": strip_tags(form.get("name"), 80),
        "email": strip_tags(form.get("email"), 120),
        "phone": strip_tags(form.get("phone"), 20),
        "message": strip_tags(form.get("message"), 1000),
    }
    errors = []

    if not data["name"]:
        errors.append("Name is required.")
    if not data["email"] or not EMAIL_RE.match(data["email"]):
        errors.append("Enter a valid email address.")
    if not data["message"]:
        errors.append("Message is required.")
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors.append("Enter a valid phone number.")

    return data, errors



# PWA route
@app.route("/sw.js")
def service_worker():
    """Serve the service worker from the site root so it can control the full PWA."""
    return send_from_directory("static/js", "sw.js", mimetype="application/javascript")


# Public website routes
@app.route("/")
def index():
    """Display the homepage with hero content and service tiles."""
    services = get_all_services()
    return render_template("index.html", services=services)


@app.route("/services")
def services():
    """Display the full public list of available installation services."""
    services = get_all_services()
    return render_template("services.html", services=services)


@app.route("/services/<slug>", methods=["GET"])
def service_detail(slug):
    """Display one service page, including the booking form for that service."""
    service = get_service_by_slug(slug)
    if service is None:
        abort(404)
    return render_template("service_detail.html", service=service, form_data={})


@app.route("/book/<slug>", methods=["POST"])
def make_booking(slug):
    """Validate a customer booking request and store it in the database."""
    service = get_service_by_slug(slug)
    if service is None:
        abort(404)

    data, errors = validate_booking_form(request.form)
    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("service_detail.html", service=service, form_data=data), 400

    # Each booking gets a unique reference such as RH-1234 for the customer confirmation page.
    booking_ref = generate_booking_ref()
    execute_db(
        """
        INSERT INTO bookings
            (booking_ref, customer_name, phone, car_model, service_id, preferred_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            booking_ref,
            data["customer_name"],
            data["phone"],
            data["car_model"],
            service["id"],
            data["preferred_date"],
            data["notes"],
        ),
    )
    return redirect(url_for("confirmation", booking_ref=booking_ref))


@app.route("/confirmation/<booking_ref>")
def confirmation(booking_ref):
    """Show the customer a summary of the booking after the form is submitted."""
    booking = query_db(
        """
        SELECT b.*, s.name AS service_name
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.booking_ref = ?
        """,
        (booking_ref,),
        one=True,
    )
    if booking is None:
        abort(404)
    return render_template("confirmation.html", booking=booking)


@app.route("/about")
def about():
    """Display business information about Royal Himalayans."""
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    """Display the contact form and save valid customer inquiries."""
    form_data = {}
    if request.method == "POST":
        form_data, errors = validate_inquiry_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("contact.html", form_data=form_data), 400

        execute_db(
            "INSERT INTO inquiries (name, email, phone, message) VALUES (?, ?, ?, ?)",
            (form_data["name"], form_data["email"], form_data["phone"], form_data["message"]),
        )
        flash("Thank you. Your inquiry has been submitted.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html", form_data=form_data)



# Admin authentication routes
@app.route("/admin")
def admin_index():
    """Redirect the admin root to either the dashboard or login page."""
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Check admin login details using bcrypt and create a secure session."""
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = strip_tags(request.form.get("username"), 50)
        password = request.form.get("password", "")
        admin = query_db("SELECT * FROM admins WHERE username = ?", (username,), one=True)

        # The password is checked against the stored bcrypt hash, not plain text.
        if admin and bcrypt.check_password_hash(admin["password_hash"], password):
            session.clear()
            session.permanent = True
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Login successful.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    """Terminate the current admin session and return to the login page."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


# Admin management routes
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    """Display booking statistics and the five most recent bookings."""
    stats = {
        "total": query_db("SELECT COUNT(*) AS total FROM bookings", one=True)["total"],
        "pending": query_db("SELECT COUNT(*) AS total FROM bookings WHERE status = ?", ("Pending",), one=True)["total"],
        "confirmed": query_db("SELECT COUNT(*) AS total FROM bookings WHERE status = ?", ("Confirmed",), one=True)["total"],
        "completed": query_db("SELECT COUNT(*) AS total FROM bookings WHERE status = ?", ("Completed",), one=True)["total"],
    }
    recent_bookings = query_db(
        """
        SELECT b.*, s.name AS service_name
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        ORDER BY b.created_at DESC
        LIMIT 5
        """
    )
    return render_template("admin/dashboard.html", stats=stats, bookings=recent_bookings)


@app.route("/admin/bookings")
@login_required
def admin_bookings():
    """Display all bookings and allow the admin to search by customer, service or status."""
    search = strip_tags(request.args.get("q"), 100)
    if search:
        like_search = f"%{search}%"
        bookings = query_db(
            """
            SELECT b.*, s.name AS service_name
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            WHERE b.booking_ref LIKE ?
               OR b.customer_name LIKE ?
               OR b.phone LIKE ?
               OR b.car_model LIKE ?
               OR s.name LIKE ?
               OR b.status LIKE ?
            ORDER BY b.created_at DESC
            """,
            (like_search, like_search, like_search, like_search, like_search, like_search),
        )
    else:
        bookings = query_db(
            """
            SELECT b.*, s.name AS service_name
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            ORDER BY b.created_at DESC
            """
        )
    return render_template("admin/bookings.html", bookings=bookings, search=search)


@app.route("/admin/bookings/<int:booking_id>", methods=["GET", "POST"])
@login_required
def admin_booking_detail(booking_id):
    """Allow the admin to view and update one booking record."""
    booking = query_db(
        """
        SELECT b.*, s.name AS service_name
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.id = ?
        """,
        (booking_id,),
        one=True,
    )
    if booking is None:
        abort(404)

    services = get_all_services()

    if request.method == "POST":
        data, errors = validate_booking_form(request.form)
        service_id = strip_tags(request.form.get("service_id"), 10)
        status = strip_tags(request.form.get("status"), 20)

        # Convert the selected service id from form text to an integer before checking it exists.
        try:
            service_id_int = int(service_id)
        except ValueError:
            service_id_int = 0

        service_exists = query_db("SELECT id FROM services WHERE id = ?", (service_id_int,), one=True)
        if service_exists is None:
            errors.append("Select a valid service.")
        if status not in STATUS_OPTIONS:
            errors.append("Select a valid status.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "admin/booking_detail.html",
                booking=booking,
                services=services,
                status_options=STATUS_OPTIONS,
            ), 400

        execute_db(
            """
            UPDATE bookings
            SET customer_name = ?, phone = ?, car_model = ?, service_id = ?,
                preferred_date = ?, status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["customer_name"],
                data["phone"],
                data["car_model"],
                service_id_int,
                data["preferred_date"],
                status,
                data["notes"],
                booking_id,
            ),
        )
        flash("Booking updated successfully.", "success")
        return redirect(url_for("admin_booking_detail", booking_id=booking_id))

    return render_template(
        "admin/booking_detail.html",
        booking=booking,
        services=services,
        status_options=STATUS_OPTIONS,
    )


@app.route("/admin/inquiries")
@login_required
def admin_inquiries():
    """Display contact form inquiries for admin review."""
    inquiries = query_db("SELECT * FROM inquiries ORDER BY created_at DESC")
    return render_template("admin/inquiries.html", inquiries=inquiries)


@app.route("/admin/services")
@login_required
def admin_services():
    """Display the seeded services in a read-only admin table."""
    services = get_all_services(active_only=False)
    return render_template("admin/services.html", services=services)


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Show a custom page when a route or record cannot be found."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    """Show a generic page if the server encounters an unexpected error."""
    return render_template("500.html"), 500


if __name__ == "__main__":
    # Debug mode is only for local development, not production deployment.
    app.run(debug=True)

"""SQLite database helpers for the Royal Himalayans booking system.

The database layer is kept in this separate file so app.py can focus on routes
and user actions. All database access uses parameterised SQL queries, which is a
key security requirement because it reduces SQL injection risk.
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime
from typing import Any

from flask import current_app, g


# Starter services inserted into the services table when the database is empty.
# The slug is used in URLs, while image_filename links each service to a PNG file.
SERVICE_SEED = [
    {
        "name": "Android Head Units",
        "slug": "android-head-units",
        "short_description": "Latest Android systems with premium features.",
        "description": "Upgrade your factory stereo with a modern Android head unit for navigation, music, Bluetooth, reversing camera support and app connectivity.",
        "features": "Large touch screen|Bluetooth and Wi-Fi|Google Maps and media apps|Reverse camera support|Professional installation",
        "price_from": 599,
        "image_filename": "android-head-units.png",
    },
    {
        "name": "Apple CarPlay",
        "slug": "apple-carplay",
        "short_description": "Seamless iPhone connectivity.",
        "description": "Apple CarPlay provides safer access to calls, maps, messages and music through your vehicle display.",
        "features": "Wireless and wired connectivity|Voice control support|GPS navigation|Compatible with most vehicles|Professional installation",
        "price_from": 499,
        "image_filename": "apple-carplay.png",
    },
    {
        "name": "Android Auto",
        "slug": "android-auto",
        "short_description": "Smart and simple connectivity.",
        "description": "Android Auto connects your phone to your vehicle display for maps, calls, messages and entertainment.",
        "features": "Google Maps integration|Voice control|Music and messaging apps|Hands-free calling|Professional installation",
        "price_from": 499,
        "image_filename": "android-auto.png",
    },
    {
        "name": "Dash Cams",
        "slug": "dash-cams",
        "short_description": "High quality recording for your safety.",
        "description": "Dash camera installation for reliable road recording, incident evidence and peace of mind.",
        "features": "Front and rear options|Loop recording|Parking mode support|Clean wiring|Professional installation",
        "price_from": 299,
        "image_filename": "dash-cams.png",
    },
    {
        "name": "Parking Sensors",
        "slug": "parking-sensors",
        "short_description": "Park with confidence every time.",
        "description": "Parking sensors help reduce blind spots and make everyday parking safer and easier.",
        "features": "Front or rear sensors|Audible alerts|Neat bumper installation|Colour matched options|Professional installation",
        "price_from": 249,
        "image_filename": "parking-sensors.png",
    },
]


def get_db() -> sqlite3.Connection:
    """Return one SQLite connection for the current Flask request.

    Flask's g object stores data for only the current request. This means each
    request reuses one connection, then close_db() closes it at the end.
    """
    if "db" not in g:
        db_path = current_app.config.get("DATABASE_PATH", "royal_himalayans.db")
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row

        # Foreign key support must be enabled in SQLite so booking.service_id is enforced.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error: Exception | None = None) -> None:
    """Close the database connection after Flask finishes the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query: str, args: tuple[Any, ...] = (), one: bool = False):
    """Run a SELECT query using placeholders and return rows.

    The args tuple is passed separately from the SQL string. This is safer than
    building SQL with string concatenation because user input is treated as data.
    """
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query: str, args: tuple[Any, ...] = ()) -> int:
    """Run an INSERT, UPDATE or DELETE query and commit the change."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def init_db(bcrypt) -> None:
    """Create database tables and seed initial records if needed."""
    db = get_db()

    # CREATE TABLE IF NOT EXISTS allows the app to start even when the tables already exist.
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            short_description TEXT NOT NULL,
            description TEXT NOT NULL,
            features TEXT NOT NULL,
            price_from INTEGER NOT NULL,
            image_filename TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car_model TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            preferred_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Seed the services only once. Existing services are not duplicated on restart.
    service_count = db.execute("SELECT COUNT(*) AS total FROM services").fetchone()["total"]
    if service_count == 0:
        db.executemany(
            """
            INSERT INTO services
                (name, slug, short_description, description, features, price_from, image_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    service["name"],
                    service["slug"],
                    service["short_description"],
                    service["description"],
                    service["features"],
                    service["price_from"],
                    service["image_filename"],
                )
                for service in SERVICE_SEED
            ],
        )

    # Create a default admin account only if no admin users exist yet.
    admin_count = db.execute("SELECT COUNT(*) AS total FROM admins").fetchone()["total"]
    if admin_count == 0:
        default_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        password_hash = bcrypt.generate_password_hash(default_password).decode("utf-8")
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", password_hash),
        )

    db.commit()


def get_all_services(active_only: bool = True):
    """Return all services for the public site or admin services table."""
    if active_only:
        return query_db("SELECT * FROM services WHERE active = ? ORDER BY id", (1,))
    return query_db("SELECT * FROM services ORDER BY id")


def get_service_by_slug(slug: str):
    """Return one active service using the slug from the URL."""
    return query_db("SELECT * FROM services WHERE slug = ? AND active = ?", (slug, 1), one=True)


def get_service_by_id(service_id: int):
    """Return one service by database id."""
    return query_db("SELECT * FROM services WHERE id = ?", (service_id,), one=True)


def generate_booking_ref() -> str:
    """Generate a unique booking reference in RH-#### format."""
    for _ in range(100):
        ref = f"RH-{random.randint(1000, 9999)}"
        existing = query_db("SELECT id FROM bookings WHERE booking_ref = ?", (ref,), one=True)
        if existing is None:
            return ref

    # Very unlikely fallback: include the current minute/second to reduce collision chance.
    return "RH-" + datetime.now().strftime("%M%S")

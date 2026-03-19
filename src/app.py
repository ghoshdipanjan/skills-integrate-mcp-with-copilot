"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.

Uses SQLite for persistent storage so data survives server restarts.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import sqlite3
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Database setup
DATA_DIR = Path(os.getenv("HSMS_DATA_DIR", current_dir.parent / "data"))
DB_PATH = Path(os.getenv("HSMS_DB_PATH", str(DATA_DIR / "activities.db")))


def get_db():
    """Get a database connection."""
    # Ensure the directory for the database file exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database schema and seed data if empty."""
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS participants (
                activity_name TEXT NOT NULL,
                email TEXT NOT NULL,
                PRIMARY KEY (activity_name, email),
                FOREIGN KEY (activity_name) REFERENCES activities(name)
                    ON DELETE CASCADE ON UPDATE CASCADE
            );
        """)

        # Seed data only if the activities table is empty
        count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        if count == 0:
            seed_data = [
                ("Chess Club", "Learn strategies and compete in chess tournaments",
                 "Fridays, 3:30 PM - 5:00 PM", 12),
                ("Programming Class", "Learn programming fundamentals and build software projects",
                 "Tuesdays and Thursdays, 3:30 PM - 4:30 PM", 20),
                ("Gym Class", "Physical education and sports activities",
                 "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM", 30),
                ("Soccer Team", "Join the school soccer team and compete in matches",
                 "Tuesdays and Thursdays, 4:00 PM - 5:30 PM", 22),
                ("Basketball Team", "Practice and play basketball with the school team",
                 "Wednesdays and Fridays, 3:30 PM - 5:00 PM", 15),
                ("Art Club", "Explore your creativity through painting and drawing",
                 "Thursdays, 3:30 PM - 5:00 PM", 15),
                ("Drama Club", "Act, direct, and produce plays and performances",
                 "Mondays and Wednesdays, 4:00 PM - 5:30 PM", 20),
                ("Math Club", "Solve challenging problems and participate in math competitions",
                 "Tuesdays, 3:30 PM - 4:30 PM", 10),
                ("Debate Team", "Develop public speaking and argumentation skills",
                 "Fridays, 4:00 PM - 5:30 PM", 12),
            ]
            conn.executemany(
                "INSERT INTO activities (name, description, schedule, max_participants) VALUES (?, ?, ?, ?)",
                seed_data
            )

            seed_participants = [
                ("Chess Club", "michael@mergington.edu"),
                ("Chess Club", "daniel@mergington.edu"),
                ("Programming Class", "emma@mergington.edu"),
                ("Programming Class", "sophia@mergington.edu"),
                ("Gym Class", "john@mergington.edu"),
                ("Gym Class", "olivia@mergington.edu"),
                ("Soccer Team", "liam@mergington.edu"),
                ("Soccer Team", "noah@mergington.edu"),
                ("Basketball Team", "ava@mergington.edu"),
                ("Basketball Team", "mia@mergington.edu"),
                ("Art Club", "amelia@mergington.edu"),
                ("Art Club", "harper@mergington.edu"),
                ("Drama Club", "ella@mergington.edu"),
                ("Drama Club", "scarlett@mergington.edu"),
                ("Math Club", "james@mergington.edu"),
                ("Math Club", "benjamin@mergington.edu"),
                ("Debate Team", "charlotte@mergington.edu"),
                ("Debate Team", "henry@mergington.edu"),
            ]
            conn.executemany(
                "INSERT INTO participants (activity_name, email) VALUES (?, ?)",
                seed_participants
            )

        conn.commit()
    finally:
        conn.close()


# Initialize the database on startup
init_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    """Get all activities with their participants."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT name, description, schedule, max_participants FROM activities").fetchall()
        result = {}
        for row in rows:
            participants = conn.execute(
                "SELECT email FROM participants WHERE activity_name = ?",
                (row["name"],)
            ).fetchall()
            result[row["name"]] = {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": [p["email"] for p in participants],
            }
        return result
    finally:
        conn.close()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    conn = get_db()
    try:
        # Validate activity exists
        activity = conn.execute(
            "SELECT name, max_participants FROM activities WHERE name = ?",
            (activity_name,)
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Validate student is not already signed up
        existing = conn.execute(
            "SELECT 1 FROM participants WHERE activity_name = ? AND email = ?",
            (activity_name, email)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        # Add student
        conn.execute(
            "INSERT INTO participants (activity_name, email) VALUES (?, ?)",
            (activity_name, email)
        )
        conn.commit()
        return {"message": f"Signed up {email} for {activity_name}"}
    finally:
        conn.close()


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    conn = get_db()
    try:
        # Validate activity exists
        activity = conn.execute(
            "SELECT name FROM activities WHERE name = ?",
            (activity_name,)
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Validate student is signed up
        existing = conn.execute(
            "SELECT 1 FROM participants WHERE activity_name = ? AND email = ?",
            (activity_name, email)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        # Remove student
        conn.execute(
            "DELETE FROM participants WHERE activity_name = ? AND email = ?",
            (activity_name, email)
        )
        conn.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
    finally:
        conn.close()

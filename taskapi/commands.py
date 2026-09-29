"""Flask CLI commands: `flask --app taskapi init-db` and `flask --app taskapi seed`."""
from datetime import date, timedelta

import click

from .extensions import db
from .models import Task, User
from .security import hash_password

# (title, description, done, due date as "days from the day you seed" or None)
DEMO_TASKS = [
    ("Pick the app idea and write the scope", "In: tasks with due dates. Out: sharing.", True, -12),
    ("Write user stories for the task list", None, True, -10),
    ("Create the Vite React project", None, True, None),
    ("Sketch a text wireframe for every screen", "List, detail, form, login, 404.", True, -7),
    ("Map each screen to an API endpoint", None, True, -5),
    ("Add React Router and a page shell", None, False, -1),
    ("Show a loading state on the task list", None, False, 0),
    ("Show an empty state when there are no tasks", None, True, 1),
    ("Show an error state when the API fails", None, False, 2),
    ("Add Previous and Next page buttons", "Use page and pages from the response.", False, 3),
    ("Build the task detail page", None, False, None),
    ("Build the new-task form", None, False, 5),
    ("Show field errors from a 400 response", "Read error.fields and show each message.", True, None),
    ("Build the edit form (PATCH)", None, False, 7),
    ("Ask before deleting a task", None, False, None),
    ("Refresh the list after a delete", None, False, 9),
    ("Save the token after login", "localStorage, and know the XSS trade-off.", True, None),
    ("Add a logout button", None, False, 11),
    ("Protect the task pages behind login", None, False, 12),
    ("Send the user to login on a 401", None, False, None),
    ("Show a friendly message on a 403", None, True, 14),
    ("Make the list readable on a phone", None, False, None),
    ("Deploy the frontend as a static site", None, False, 18),
    ("Add the live frontend URL to CORS_ORIGINS", None, False, 19),
    ("Run the acceptance tests and log issues", None, False, 21),
]

OTHER_TASKS = [
    ("Plan the sprint review", "Belongs to 'other'. demo should get 403 here.", False, 4),
    ("Update the project README", None, True, None),
    ("Book a study room", None, False, 6),
]

SEED_USERS = [
    ("demo", "demo-password-1", "Demo User", DEMO_TASKS),
    ("other", "other-password-1", "Other User", OTHER_TASKS),
]


def seed_database(reset=False, echo=print):
    """Create the demo users and their tasks. Existing seed users are left alone
    unless reset is True, so running it again never duplicates anything."""
    db.create_all()
    today = date.today()
    for username, password, display_name, tasks in SEED_USERS:
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if user is not None and reset:
            db.session.delete(user)  # its tasks go with it
            db.session.flush()
            user = None
        if user is not None:
            echo(f"{username}: already exists, left unchanged ({len(user.tasks)} tasks).")
            continue

        user = User(username=username, display_name=display_name,
                    password_hash=hash_password(password))
        db.session.add(user)
        db.session.flush()  # gives the user an id
        new_tasks = [
            Task(
                owner_id=user.id,
                title=title,
                description=description,
                done=done,
                due_date=None if offset is None else today + timedelta(days=offset),
            )
            for title, description, done, offset in tasks
        ]
        db.session.add_all(new_tasks)
        db.session.flush()
        echo(
            f"{username}: created (password {password}) with {len(new_tasks)} tasks, "
            f"ids {new_tasks[0].id}-{new_tasks[-1].id}."
        )
    db.session.commit()


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create any missing tables. Safe to run more than once."""
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True,
                  help="Delete the demo users and their tasks first, then recreate them.")
    def seed_command(reset):
        """Add the demo users and tasks. Safe to run more than once."""
        seed_database(reset=reset, echo=click.echo)

"""One blueprint per area of the API. create_app registers all of them."""
from . import auth, health, tasks, users

BLUEPRINTS = (health.bp, auth.bp, users.bp, tasks.bp)

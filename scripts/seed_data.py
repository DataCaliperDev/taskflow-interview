"""Seed the database with sample data for development and testing."""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import User, Task, Comment, Tag
from app.routers.auth import hash_password

init_db()

db = SessionLocal()

db.query(Comment).delete()
db.execute(Task.__table__.delete())
db.query(Tag).delete()
db.query(User).delete()
db.commit()


def get_tag(name, cache):
    if name not in cache:
        cache[name] = Tag(name=name)
        db.add(cache[name])
    return cache[name]


now = datetime.now(timezone.utc)
tag_cache = {}

alice = User(username="alice", email="alice@example.com",
             password_hash=hash_password("alice123"), role="admin")
bob = User(username="bob", email="bob@example.com",
           password_hash=hash_password("bob123"), role="member")
carol = User(username="carol", email="carol@example.com",
             password_hash=hash_password("carol123"), role="member")

db.add_all([alice, bob, carol])
db.commit()

tasks_data = [
    Task(title="Set up CI/CD pipeline", description="Configure GitHub Actions for automated testing.",
         status="in_progress", priority=3, owner_id=alice.id,
         tags=[get_tag("devops", tag_cache), get_tag("infra", tag_cache)],
         due_date=now + timedelta(days=3)),
    Task(title="Write API documentation", description="Document all endpoints using OpenAPI.",
         status="todo", priority=2, owner_id=alice.id,
         tags=[get_tag("docs", tag_cache)]),
    Task(title="Fix login page bug", description="Users are redirected to a blank page after login.",
         status="todo", priority=3, owner_id=bob.id,
         due_date=now - timedelta(days=1)),
    Task(title="Add unit tests for helpers", description=None,
         status="todo", priority=1, owner_id=bob.id,
         tags=[get_tag("testing", tag_cache)]),
    Task(title="Migrate database to Postgres", description="Move from SQLite to PostgreSQL for production.",
         status="done", priority=2, owner_id=carol.id,
         tags=[get_tag("db", tag_cache), get_tag("infra", tag_cache)]),
    Task(title="Code review for PR #42", description=None,
         status="done", priority=1, owner_id=carol.id),
]

db.add_all(tasks_data)
db.commit()

comments = [
    Comment(content="Started the pipeline setup - blocked on secrets config.",
            task_id=tasks_data[0].id, author_id=bob.id),
    Comment(content="Docs template is in Confluence, linking there.",
            task_id=tasks_data[1].id, author_id=carol.id),
]
db.add_all(comments)
db.commit()

db.close()
print("Database seeded successfully.")
print("Users: alice (admin, pw: alice123), bob (pw: bob123), carol (pw: carol123)")

"""Migrate the legacy comma-separated tasks.tags column into the tags / task_tags tables.

Run once after upgrading to the normalised tag schema:

    python scripts/migrate_tags.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app.database import SessionLocal, engine, init_db
from app.models import Tag, task_tags


def column_exists(table: str, column: str) -> bool:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def migrate() -> None:
    init_db()

    if not column_exists("tasks", "tags"):
        print("No legacy 'tags' column found - nothing to migrate.")
        return

    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, tags FROM tasks")).fetchall()
        tag_cache = {tag.name: tag for tag in db.query(Tag).all()}
        migrated = 0

        for task_id, tags_str in rows:
            if not tags_str:
                continue
            names = [t.strip() for t in tags_str.split(",") if t.strip()]
            for name in names:
                tag = tag_cache.get(name)
                if tag is None:
                    tag = Tag(name=name)
                    db.add(tag)
                    db.flush()
                    tag_cache[name] = tag
                exists = db.execute(
                    task_tags.select().where(
                        (task_tags.c.task_id == task_id)
                        & (task_tags.c.tag_id == tag.id)
                    )
                ).first()
                if not exists:
                    db.execute(
                        task_tags.insert().values(task_id=task_id, tag_id=tag.id)
                    )
                    migrated += 1

        db.commit()
        print(f"Migrated {migrated} task-tag associations.")
        print("You may now drop the legacy 'tasks.tags' column.")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

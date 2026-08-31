"""Conversations with context management and long-term memory.

Revision ID: 0004_conversations
Revises: 0003_content_integrations
"""
from alembic import op

revision = "0004_conversations"
down_revision = "0003_content_integrations"
branch_labels = None
depends_on = None

NEW_TABLES = ["conversations", "conversation_messages"]


def upgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from sqlalchemy import inspect
    existing = set(inspect(op.get_bind()).get_table_names())
    for table in reversed(NEW_TABLES):
        if table in existing:
            op.drop_table(table)

"""Requirements, documents, attachments and enterprise integrations.

Revision ID: 0003_content_integrations
Revises: 0002_enterprise_runtime
"""
from alembic import op

revision = "0003_content_integrations"
down_revision = "0002_enterprise_runtime"
branch_labels = None
depends_on = None

NEW_TABLES = ["requirement_versions", "project_documents", "project_attachments", "requirement_clarifications"]


def upgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from sqlalchemy import inspect
    existing = set(inspect(op.get_bind()).get_table_names())
    for table in reversed(NEW_TABLES):
        if table in existing: op.drop_table(table)

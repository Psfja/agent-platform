"""Enterprise runtime: RBAC, queue, checkpoints, agent config and operations.

Revision ID: 0002_enterprise_runtime
Revises: 0001_platform_baseline
"""
from alembic import op

revision = "0002_enterprise_runtime"
down_revision = "0001_platform_baseline"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "agent_types", "agent_type_versions", "pipeline_templates", "pipeline_nodes",
    "agent_checkpoints", "database_backups", "notifications",
]


def upgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    existing = set(inspect(bind).get_table_names())
    for table in reversed(NEW_TABLES):
        if table in existing:
            op.drop_table(table)

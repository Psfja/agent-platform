"""Platform baseline schema.

Revision ID: 0001_platform_baseline
Revises: None
"""
from alembic import op

revision = "0001_platform_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The baseline deliberately uses shared SQLAlchemy metadata so fresh SQLite
    # and PostgreSQL installations receive the same complete schema. Future
    # changes must use explicit Alembic operations in new revisions.
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=op.get_bind())

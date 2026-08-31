"""AgentType temperature (real model sampling knob).

Revision ID: 0006_agent_type_temperature
Revises: 0005_conversation_agent
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_agent_type_temperature"
down_revision = "0005_conversation_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    agent_cols = {c["name"] for c in inspector.get_columns("agent_types")}
    if "temperature" not in agent_cols:
        op.add_column("agent_types", sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"))
    build_cols = {c["name"] for c in inspector.get_columns("agent_builds")}
    if "temperature" not in build_cols:
        op.add_column("agent_builds", sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"))


def downgrade() -> None:
    from sqlalchemy import inspect
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns("agent_types")}
    if "temperature" in cols and op.get_bind().dialect.name != "sqlite":
        op.drop_column("agent_types", "temperature")
    # SQLite 无法可靠删列，降级保留该列

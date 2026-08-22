"""Conversation agent mode: DeepAgents runtime with tools, interrupts and workspace.

Revision ID: 0005_conversation_agent
Revises: 0004_conversations
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_conversation_agent"
down_revision = "0004_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    conversation_cols = {col["name"] for col in inspector.get_columns("conversations")}
    if "mode" not in conversation_cols:
        op.add_column("conversations", sa.Column("mode", sa.String(16), nullable=False, server_default="chat"))
        op.create_index("ix_conversations_mode", "conversations", ["mode"])
    # 中断表由 metadata.create_all 创建
    from app.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from sqlalchemy import inspect
    existing = set(inspect(op.get_bind()).get_table_names())
    if "conversation_interrupts" in existing:
        op.drop_table("conversation_interrupts")
    # mode 列与索引保留（避免破坏既有数据），降级仅移除中断表

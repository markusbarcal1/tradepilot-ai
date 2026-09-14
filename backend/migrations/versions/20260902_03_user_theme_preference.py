"""Add per-user theme preference."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_03"
down_revision = "20260829_02"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_preferences") as batch:
        batch.add_column(sa.Column("theme", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("user_preferences") as batch:
        batch.drop_column("theme")

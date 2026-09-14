"""Create the existing paper-trading schema baseline."""

from alembic import op
import sqlalchemy as sa


revision = "20260828_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("starting_cash", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.Text(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.Text(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )


def downgrade():
    op.drop_table("paper_trades")
    op.drop_table("paper_positions")
    op.drop_table("paper_account")

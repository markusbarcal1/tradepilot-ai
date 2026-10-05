"""Add global immutable earnings expectation snapshots."""

from alembic import op
import sqlalchemy as sa


revision = "20260920_04"
down_revision = "20260902_03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expectation_snapshots",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("observation_fingerprint", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Text(), nullable=True),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("expected_amount", sa.Float(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("analyst_count", sa.Integer(), nullable=True),
        sa.Column("low_amount", sa.Float(), nullable=True),
        sa.Column("high_amount", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("provider_as_of_at", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("temporal_status", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("reporting_identity", sa.JSON(), nullable=False),
        sa.Column("metric_identity", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("observation_fingerprint", name="uq_expectation_snapshots_fingerprint"),
    )
    op.create_index("ix_expectation_snapshots_lookup", "expectation_snapshots",
                    ["ticker", "fiscal_year", "fiscal_period", "metric_key", "captured_at"])


def downgrade():
    op.drop_index("ix_expectation_snapshots_lookup", table_name="expectation_snapshots")
    op.drop_table("expectation_snapshots")

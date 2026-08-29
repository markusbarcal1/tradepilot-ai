"""Add multi-user ownership and future user-persistence tables."""

from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "20260829_02"
down_revision = "20260828_01"
branch_labels = None
depends_on = None

LEGACY_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def upgrade():
    op.create_table(
        "app_users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("beta_status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )
    users = sa.table(
        "app_users",
        sa.column("user_id", sa.Uuid()),
        sa.column("email", sa.Text()),
        sa.column("display_name", sa.Text()),
        sa.column("beta_status", sa.Text()),
    )
    op.bulk_insert(users, [{
        "user_id": LEGACY_USER_ID,
        "email": "legacy-bootstrap@local.invalid",
        "display_name": "Legacy Local User",
        "beta_status": "active",
    }])

    op.rename_table("paper_account", "paper_accounts")
    with op.batch_alter_table("paper_accounts", recreate="always") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_paper_accounts_user_id_app_users", "app_users", ["user_id"],
            ["user_id"], ondelete="CASCADE",
        )
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE paper_accounts SET user_id = :user_id").bindparams(
            sa.bindparam("user_id", type_=sa.Uuid())
        ),
        {"user_id": LEGACY_USER_ID},
    )
    if connection.scalar(sa.text("SELECT COUNT(*) FROM paper_accounts")) == 0:
        connection.execute(
            sa.text(
                "INSERT INTO paper_accounts "
                "(user_id, cash_balance, starting_cash) VALUES (:user_id, 10000, 10000)"
            ).bindparams(sa.bindparam("user_id", type_=sa.Uuid())),
            {"user_id": LEGACY_USER_ID},
        )
    with op.batch_alter_table("paper_accounts", recreate="always") as batch:
        batch.alter_column("user_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_unique_constraint("uq_paper_accounts_user_id", ["user_id"])

    account_id = connection.scalar(sa.text("SELECT MIN(id) FROM paper_accounts"))
    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table(
        "paper_positions", recreate="always", naming_convention=naming
    ) as batch:
        batch.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_paper_positions_account_id_paper_accounts", "paper_accounts",
            ["account_id"], ["id"], ondelete="CASCADE",
        )
        batch.drop_constraint("uq_paper_positions_symbol", type_="unique")
    connection.execute(
        sa.text("UPDATE paper_positions SET account_id = :account_id"),
        {"account_id": account_id},
    )
    with op.batch_alter_table("paper_positions", recreate="always") as batch:
        batch.alter_column("account_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_paper_positions_account_symbol", ["account_id", "symbol"]
        )
        batch.create_index("ix_paper_positions_account_id", ["account_id"])

    with op.batch_alter_table("paper_trades", recreate="always") as batch:
        batch.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_paper_trades_account_id_paper_accounts", "paper_accounts",
            ["account_id"], ["id"], ondelete="CASCADE",
        )
    connection.execute(
        sa.text("UPDATE paper_trades SET account_id = :account_id"),
        {"account_id": account_id},
    )
    with op.batch_alter_table("paper_trades", recreate="always") as batch:
        batch.alter_column("account_id", existing_type=sa.Integer(), nullable=False)
        batch.create_index(
            "ix_paper_trades_account_created_at", ["account_id", "created_at"]
        )

    op.create_table(
        "watchlist_items",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "symbol"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scanner_preferences", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade():
    op.drop_table("user_preferences")
    op.drop_table("watchlist_items")
    op.drop_index("ix_paper_trades_account_created_at", table_name="paper_trades")
    with op.batch_alter_table("paper_trades", recreate="always") as batch:
        batch.drop_constraint("fk_paper_trades_account_id_paper_accounts", type_="foreignkey")
        batch.drop_column("account_id")
    op.drop_index("ix_paper_positions_account_id", table_name="paper_positions")
    with op.batch_alter_table("paper_positions", recreate="always") as batch:
        batch.drop_constraint("uq_paper_positions_account_symbol", type_="unique")
        batch.drop_constraint("fk_paper_positions_account_id_paper_accounts", type_="foreignkey")
        batch.drop_column("account_id")
        batch.create_unique_constraint("uq_paper_positions_symbol", ["symbol"])
    with op.batch_alter_table("paper_accounts", recreate="always") as batch:
        batch.drop_constraint("uq_paper_accounts_user_id", type_="unique")
        batch.drop_constraint("fk_paper_accounts_user_id_app_users", type_="foreignkey")
        batch.drop_column("user_id")
    op.rename_table("paper_accounts", "paper_account")
    op.drop_table("app_users")

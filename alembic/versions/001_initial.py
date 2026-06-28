"""initial schema

Revision ID: 001
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("company",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("exchange", sa.String(5), nullable=False),
        sa.Column("industry", sa.String(50)),
        sa.Column("business_scope", sa.Text),
        sa.Column("listing_date", sa.Date),
        sa.Column("total_shares", sa.BigInteger),
        sa.Column("float_shares", sa.BigInteger),
        sa.Column("employees", sa.Integer),
        sa.Column("website", sa.String(200)),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table("financial_summary",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("indicator", sa.String(50), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("code", "report_date", "indicator",
                            name="uq_fin_summary"),
    )

    op.create_table("financial_indicator",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("indicator", sa.String(50), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("code", "report_date", "indicator",
                            name="uq_fin_indicator"),
    )

    op.create_table("watchlist",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(50)),
        sa.Column("added_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("note", sa.String(200)),
    )

    op.create_table("position",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(50)),
        sa.Column("shares", sa.Float, nullable=False),
        sa.Column("avg_cost", sa.Float, nullable=False),
        sa.Column("buy_date", sa.Date),
        sa.Column("note", sa.String(200)),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("position")
    op.drop_table("watchlist")
    op.drop_table("financial_indicator")
    op.drop_table("financial_summary")
    op.drop_table("company")

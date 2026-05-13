"""watchlist: columnas plan valoración (general, banks, REIT) + caché ajuste

Revision ID: wlvalplan01
Revises: jobprogress01
Create Date: 2026-05-09

Alineado con docs/implementaciones/WATCHLIST_VALORACION_PLAN_IMPLEMENTACION.md.
Fórmulas por modo: fases posteriores; aquí solo esquema persistente.
"""

from alembic import op
import sqlalchemy as sa


revision = "wlvalplan01"
down_revision = "jobprogress01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        # --- Modo general (niveles A/B/C y caché) ---
        batch_op.add_column(sa.Column("per_fair", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cagr_eps_yoy", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("net_debt_to_ebitda", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("fcf_to_net_income", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("ebitda_margin_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("operating_margin_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("roic_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("target_price_5yr_gross", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("valuation_adjustment_factor", sa.Float(), nullable=True)
        )

        # --- Modo banks ---
        batch_op.add_column(sa.Column("price_to_book", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pb_fair", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("roe_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cet1_ratio_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("npl_ratio_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cost_to_income_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("nim_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bvps", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("loan_to_deposit_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cost_of_risk_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bvps_cagr_yoy", sa.Float(), nullable=True))

        # --- Modo real estate / REIT ---
        batch_op.add_column(sa.Column("ffo_per_share", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("affo_per_share", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("price_to_ffo", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("p_ffo_fair", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cagr_ffo_yoy", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("reit_leverage_ratio", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("reit_leverage_kind", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(sa.Column("occupancy_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("walt_years", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("same_store_growth_pct", sa.Float(), nullable=True)
        )


def downgrade():
    cols = [
        "same_store_growth_pct",
        "walt_years",
        "occupancy_pct",
        "reit_leverage_kind",
        "reit_leverage_ratio",
        "cagr_ffo_yoy",
        "p_ffo_fair",
        "price_to_ffo",
        "affo_per_share",
        "ffo_per_share",
        "bvps_cagr_yoy",
        "cost_of_risk_pct",
        "loan_to_deposit_pct",
        "bvps",
        "nim_pct",
        "cost_to_income_pct",
        "npl_ratio_pct",
        "cet1_ratio_pct",
        "roe_pct",
        "pb_fair",
        "price_to_book",
        "valuation_adjustment_factor",
        "target_price_5yr_gross",
        "roic_pct",
        "operating_margin_pct",
        "ebitda_margin_pct",
        "fcf_to_net_income",
        "net_debt_to_ebitda",
        "cagr_eps_yoy",
        "per_fair",
    ]
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        for c in cols:
            batch_op.drop_column(c)

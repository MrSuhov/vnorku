"""add_delivery_fixed_fee_to_lsd_configs

Revision ID: 6a28cce43686
Revises: 8fdc257facdb
Create Date: 2025-09-30 10:14:08.292266

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a28cce43686'
down_revision = '8fdc257facdb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add delivery_fixed_fee column to lsd_configs table
    op.add_column('lsd_configs', sa.Column('delivery_fixed_fee', sa.Numeric(10, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove delivery_fixed_fee column from lsd_configs table
    op.drop_column('lsd_configs', 'delivery_fixed_fee')

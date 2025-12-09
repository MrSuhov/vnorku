"""remove_unused_fields_from_lsd_configs

Revision ID: 8fdc257facdb
Revises: 9667ea8bd89b
Create Date: 2025-09-30 09:52:53.166777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8fdc257facdb'
down_revision = '9667ea8bd89b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove unused fields from lsd_configs table
    op.drop_column('lsd_configs', 'api_endpoints')
    op.drop_column('lsd_configs', 'auth_config')
    op.drop_column('lsd_configs', 'auth_url')


def downgrade() -> None:
    # Add back the removed columns for rollback
    op.add_column('lsd_configs', sa.Column('auth_url', sa.Text(), nullable=True))
    op.add_column('lsd_configs', sa.Column('auth_config', sa.JSON(), nullable=True))
    op.add_column('lsd_configs', sa.Column('api_endpoints', sa.JSON(), nullable=True))

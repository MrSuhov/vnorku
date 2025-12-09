"""merge_heads

Revision ID: d47bbb054e63
Revises: 2025_09_27_alternatives, e8f9a1b2c3d4
Create Date: 2025-09-27 13:35:50.903760

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd47bbb054e63'
down_revision = ('2025_09_27_alternatives', 'e8f9a1b2c3d4')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""merge_multiple_heads

Revision ID: 9667ea8bd89b
Revises: c608fde7044b, basket_rank_field, add_lowercase_enum_values
Create Date: 2025-09-30 09:13:34.939780

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9667ea8bd89b'
down_revision = ('c608fde7044b', 'basket_rank_field', 'add_lowercase_enum_values')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

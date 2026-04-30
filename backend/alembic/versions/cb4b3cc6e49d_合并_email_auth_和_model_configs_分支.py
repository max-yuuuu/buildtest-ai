"""\合并 email_auth 和 model_configs 分支"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cb4b3cc6e49d'
down_revision: Union[str, None] = ('0012_email_auth', '0013_add_model_config_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""add task zip code"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_000002"
down_revision = "20260324_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("watch_tasks", sa.Column("zip_code", sa.String(length=32), nullable=True))
    op.execute(
        """
        UPDATE watch_tasks
        SET zip_code = COALESCE(
            (
                SELECT user_preferences.default_zip_code
                FROM user_preferences
                WHERE user_preferences.user_id = watch_tasks.user_id
            ),
            '00000'
        )
        """
    )
    op.alter_column("watch_tasks", "zip_code", existing_type=sa.String(length=32), nullable=False)


def downgrade() -> None:
    op.drop_column("watch_tasks", "zip_code")

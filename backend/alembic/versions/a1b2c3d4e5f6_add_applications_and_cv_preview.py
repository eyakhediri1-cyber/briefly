"""add job applications and cv preview columns

Revision ID: a1b2c3d4e5f6
Revises: 7e57014f7569
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7e57014f7569'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailored_cvs', sa.Column('original_sections', sa.JSON(), nullable=True))
    op.add_column('tailored_cvs', sa.Column('preview_summary', sa.JSON(), nullable=True))

    op.create_table(
        'job_applications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('job_posting_id', sa.Uuid(), nullable=False),
        sa.Column('tailored_cv_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('tailored_cv_snapshot', sa.JSON(), nullable=False),
        sa.Column('applied_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tailored_cv_id'], ['tailored_cvs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('job_applications')
    op.drop_column('tailored_cvs', 'preview_summary')
    op.drop_column('tailored_cvs', 'original_sections')

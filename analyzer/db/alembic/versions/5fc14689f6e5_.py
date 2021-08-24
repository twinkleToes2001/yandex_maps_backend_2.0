"""empty message

Revision ID: 5fc14689f6e5
Revises: 
Create Date: 2021-08-22 10:20:18.362977

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

from analyzer.api import DEFAULT_PLACES
from analyzer.db.schema import places_table as places_t

# revision identifiers, used by Alembic.
revision = '5fc14689f6e5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('places',
    sa.Column('place_uid', sa.String(), nullable=False),
    sa.Column('place_id', sa.BigInteger(), nullable=False),
    sa.Column('place_title', sa.String(), nullable=True),
    sa.Column('coordinates', Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=True),
    sa.PrimaryKeyConstraint('place_uid', name=op.f('pk__places'))
    )
    op.create_table('users',
    sa.Column('user_email', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('user_email', name=op.f('pk__users'))
    )
    op.create_table('user_feedbacks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_email', sa.String(), nullable=False),
    sa.Column('place_uid', sa.String(), nullable=False),
    sa.Column('feedback_rate', sa.Integer(), nullable=False),
    sa.Column('feedback_text', sa.Text(), nullable=False),
    sa.CheckConstraint('feedback_rate >= 0 AND feedback_rate <= 5', name=op.f('ck__user_feedbacks__feedback_rate')),
    sa.ForeignKeyConstraint(['place_uid'], ['places.place_uid'], name=op.f('fk__user_feedbacks__place_uid__places')),
    sa.ForeignKeyConstraint(['user_email'], ['users.user_email'], name=op.f('fk__user_feedbacks__user_email__users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk__user_feedbacks')),
    sa.UniqueConstraint('user_email', 'place_uid')
    )
    op.create_table('user_places',
    sa.Column('user_email', sa.String(), nullable=False),
    sa.Column('place_uid', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['place_uid'], ['places.place_uid'], name=op.f('fk__user_places__place_uid__places')),
    sa.ForeignKeyConstraint(['user_email'], ['users.user_email'], name=op.f('fk__user_places__user_email__users')),
    sa.PrimaryKeyConstraint('user_email', 'place_uid', name=op.f('pk__user_places'))
    )
    # INSERT INTO places (place_uid, place_id, place_title, coordinates)
    # VALUES
    # ('ymapsbm1://org?oid=1627768090', 2237273830, 'DEFAULT_PLACE', 'POINT(56.173378 58.000049)'),
    # ('ymapsbm1://org?oid=1627768091', 2237273831, 'DEFAULT_PLACE', 'POINT(44.173378 44.000049)'),
    # ('ymapsbm1://org?oid=1627768092', 2237273832, 'DEFAULT_PLACE', 'POINT(33.173378 33.000049)'),
    # ('ymapsbm1://org?oid=1627768093', 2237273833, 'DEFAULT_PLACE', 'POINT(22.173378 22.000049)'),
    # ('ymapsbm1://org?oid=1627768094', 2237273834, 'DEFAULT_PLACE', 'POINT(11.173378 11.000049)')
    # ON CONFLICT DO NOTHING;
    op.bulk_insert(
        places_t,
        [
            {"place_uid": p_uid, "place_id": p_id,
             "place_title": 'DEFAULT_PLACE',
             "coordinates": 'POINT({} {})'.format(lon, lat)}
            for p_uid, p_id, lat, lon in DEFAULT_PLACES
        ]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_places')
    op.drop_table('user_feedbacks')
    op.drop_table('users')
    op.drop_table('places')
    # ### end Alembic commands ###

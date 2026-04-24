"""Geo reference tables: ref_states, ref_counties, ref_zip_codes

Revision ID: 002
Revises: 001
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ref_states",
        sa.Column("fips_code", sa.String(2), primary_key=True),
        sa.Column("usps_code", sa.String(2), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
    )
    op.create_index("uq_ref_states_usps_code", "ref_states", ["usps_code"], unique=True)

    op.create_table(
        "ref_counties",
        sa.Column("geoid", sa.String(5), primary_key=True),
        sa.Column("state_fips", sa.String(2), nullable=False),
        sa.Column("county_fips", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "state_usps",
            sa.String(2),
            sa.ForeignKey("ref_states.usps_code", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index("ix_ref_counties_state_usps", "ref_counties", ["state_usps"])
    op.create_index("ix_ref_counties_name_state", "ref_counties", ["name", "state_usps"])

    op.create_table(
        "ref_zip_codes",
        sa.Column("zip_code", sa.String(5), primary_key=True),
        sa.Column("primary_city", sa.String(50), nullable=False),
        sa.Column(
            "state_usps",
            sa.String(2),
            sa.ForeignKey("ref_states.usps_code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "county_geoid",
            sa.String(5),
            sa.ForeignKey("ref_counties.geoid", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
    )
    op.create_index("ix_ref_zip_codes_state_usps", "ref_zip_codes", ["state_usps"])
    op.create_index("ix_ref_zip_codes_county_geoid", "ref_zip_codes", ["county_geoid"])

    # Seed ref_states: 50 states + DC + 5 territories = 56 total
    # FIPS codes per ANSI INCITS 38:2009 (formerly FIPS 5-2)
    op.execute("""
        INSERT INTO ref_states (fips_code, usps_code, name) VALUES
        ('01','AL','Alabama'),
        ('02','AK','Alaska'),
        ('04','AZ','Arizona'),
        ('05','AR','Arkansas'),
        ('06','CA','California'),
        ('08','CO','Colorado'),
        ('09','CT','Connecticut'),
        ('10','DE','Delaware'),
        ('11','DC','District of Columbia'),
        ('12','FL','Florida'),
        ('13','GA','Georgia'),
        ('15','HI','Hawaii'),
        ('16','ID','Idaho'),
        ('17','IL','Illinois'),
        ('18','IN','Indiana'),
        ('19','IA','Iowa'),
        ('20','KS','Kansas'),
        ('21','KY','Kentucky'),
        ('22','LA','Louisiana'),
        ('23','ME','Maine'),
        ('24','MD','Maryland'),
        ('25','MA','Massachusetts'),
        ('26','MI','Michigan'),
        ('27','MN','Minnesota'),
        ('28','MS','Mississippi'),
        ('29','MO','Missouri'),
        ('30','MT','Montana'),
        ('31','NE','Nebraska'),
        ('32','NV','Nevada'),
        ('33','NH','New Hampshire'),
        ('34','NJ','New Jersey'),
        ('35','NM','New Mexico'),
        ('36','NY','New York'),
        ('37','NC','North Carolina'),
        ('38','ND','North Dakota'),
        ('39','OH','Ohio'),
        ('40','OK','Oklahoma'),
        ('41','OR','Oregon'),
        ('42','PA','Pennsylvania'),
        ('44','RI','Rhode Island'),
        ('45','SC','South Carolina'),
        ('46','SD','South Dakota'),
        ('47','TN','Tennessee'),
        ('48','TX','Texas'),
        ('49','UT','Utah'),
        ('50','VT','Vermont'),
        ('51','VA','Virginia'),
        ('53','WA','Washington'),
        ('54','WV','West Virginia'),
        ('55','WI','Wisconsin'),
        ('56','WY','Wyoming'),
        ('60','AS','American Samoa'),
        ('66','GU','Guam'),
        ('69','MP','Northern Mariana Islands'),
        ('72','PR','Puerto Rico'),
        ('78','VI','U.S. Virgin Islands')
    """)


def downgrade() -> None:
    op.drop_index("ix_ref_zip_codes_county_geoid", table_name="ref_zip_codes")
    op.drop_index("ix_ref_zip_codes_state_usps", table_name="ref_zip_codes")
    op.drop_table("ref_zip_codes")
    op.drop_index("ix_ref_counties_name_state", table_name="ref_counties")
    op.drop_index("ix_ref_counties_state_usps", table_name="ref_counties")
    op.drop_table("ref_counties")
    op.drop_index("uq_ref_states_usps_code", table_name="ref_states")
    op.drop_table("ref_states")

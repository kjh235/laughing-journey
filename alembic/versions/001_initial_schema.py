"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "license_types",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("code", sa.String(2), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sot_class", sa.SmallInteger(), nullable=True),
        sa.Column("activities", sa.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )

    op.create_table(
        "businesses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("legal_name", sa.String(100), nullable=False),
        sa.Column("dba_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(10), nullable=True),
    )

    op.create_table(
        "contact_parties",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("first_name", sa.String(50), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("title", sa.String(30), nullable=True),
    )

    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("street", sa.String(100), nullable=True),
        sa.Column("city", sa.String(50), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(5), nullable=True),
        sa.Column("zip4", sa.String(4), nullable=True),
        sa.Column("county", sa.String(50), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("geocode_source", sa.String(20), nullable=True),
    )
    op.create_index("ix_addresses_geom", "addresses", ["geom"], postgresql_using="gist")
    op.create_index("ix_addresses_zip_state", "addresses", ["zip", "state"])

    op.create_table(
        "licenses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("license_number", sa.String(20), nullable=False, unique=True),
        sa.Column("license_type_id", sa.SmallInteger(), sa.ForeignKey("license_types.id"), nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("address_id", sa.BigInteger(), sa.ForeignKey("addresses.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contact_parties.id"), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("region", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_licenses_license_number", "licenses", ["license_number"], unique=True)
    op.create_index("ix_licenses_expiration_date", "licenses", ["expiration_date"])
    op.create_index("ix_licenses_license_type_id", "licenses", ["license_type_id"])
    op.create_index("ix_licenses_business_id", "licenses", ["business_id"])
    op.create_index("ix_licenses_address_id", "licenses", ["address_id"])

    op.create_table(
        "change_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("license_id", sa.BigInteger(), sa.ForeignKey("licenses.id"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("old_data", sa.JSON(), nullable=True),
        sa.Column("new_data", sa.JSON(), nullable=True),
    )
    op.create_index("ix_change_log_license_id", "change_log", ["license_id"])
    op.create_index("ix_change_log_changed_at", "change_log", ["changed_at"])

    # Seed license_types reference data
    op.execute("""
        INSERT INTO license_types (id, code, name, description, sot_class, activities) VALUES
        (1,  '01', 'Dealer',
             'Licensed to buy and sell firearms (wholesale and retail), repair firearms, and make/fit special barrels, stocks, and trigger mechanisms.',
             NULL,
             ARRAY['sell_firearms', 'buy_firearms', 'repair_firearms']),
        (2,  '02', 'Pawnbroker',
             'Licensed to accept firearms as collateral for loans (pawn) and sell forfeited firearms.',
             NULL,
             ARRAY['pawn_firearms', 'sell_firearms']),
        (3,  '03', 'Collector of Curios and Relics',
             'Licensed to acquire, sell, and trade firearms classified as curios or relics across state lines or to other licensees. Covers pre-1899 firearms and certain collectibles.',
             NULL,
             ARRAY['collect_curios_relics', 'buy_curios_relics', 'sell_curios_relics']),
        (4,  '06', 'Ammunition Manufacturer',
             'Licensed to manufacture ammunition for firearms, excluding armor-piercing ammunition and ammunition for destructive devices.',
             NULL,
             ARRAY['manufacture_ammunition']),
        (5,  '07', 'Manufacturer of Firearms',
             'Licensed to manufacture and sell non-NFA firearms and ammunition. With Class 2 SOT, may also manufacture NFA items (suppressors, short-barreled rifles, machine guns) for government.',
             2,
             ARRAY['manufacture_firearms', 'sell_firearms', 'manufacture_ammunition']),
        (6,  '08', 'Importer of Firearms',
             'Licensed to import firearms and non-armor-piercing ammunition into the US for sale or distribution.',
             NULL,
             ARRAY['import_firearms', 'import_ammunition', 'sell_firearms']),
        (7,  '09', 'Dealer in Destructive Devices',
             'Licensed to buy and sell destructive devices (grenades, rocket launchers, large-bore weapons, etc.). Requires Class 3 SOT to deal in NFA-registered destructive devices.',
             3,
             ARRAY['sell_destructive_devices', 'buy_destructive_devices']),
        (8,  '10', 'Manufacturer of Destructive Devices',
             'Licensed to manufacture and sell destructive devices and their ammunition. Requires SOT for NFA manufacturing.',
             2,
             ARRAY['manufacture_destructive_devices', 'sell_destructive_devices']),
        (9,  '11', 'Importer of Destructive Devices',
             'Licensed to import destructive devices and their ammunition into the US.',
             1,
             ARRAY['import_destructive_devices', 'sell_destructive_devices'])
    """)


def downgrade() -> None:
    op.drop_table("change_log")
    op.drop_table("licenses")
    op.drop_index("ix_addresses_geom", table_name="addresses")
    op.drop_index("ix_addresses_zip_state", table_name="addresses")
    op.drop_table("addresses")
    op.drop_table("contact_parties")
    op.drop_table("businesses")
    op.drop_table("license_types")

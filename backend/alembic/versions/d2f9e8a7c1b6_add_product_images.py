"""add product_images metadata table

F2.22.4.D — backend metadata schema for product images.

Creates `public.product_images`, the metadata row that every uploaded
product image will eventually reference. Storage objects themselves
live in the Supabase Storage `product-images` bucket provisioned in
`supabase/migrations/20260527134127_storage_buckets.sql`; this table
holds the FastAPI-owned business metadata (which product, who
uploaded, when).

Schema (locked by docs/f2.22-contract-lock.md §8.1):

    product_images
      id                    UUID  PK     gen_random_uuid()
      product_id            UUID  NOT NULL  FK → products.id  ON DELETE CASCADE
      object_key            TEXT  NOT NULL                   (Supabase Storage key)
      uploaded_by_user_id   UUID  NOT NULL  FK → users.id    ON DELETE RESTRICT
      created_at            TIMESTAMPTZ NOT NULL  DEFAULT now()
      updated_at            TIMESTAMPTZ NOT NULL  DEFAULT now()

Constraints / indexes:
  * Primary key on id.
  * Foreign key product_id → products.id, ON DELETE CASCADE — when a
    product is hard-deleted the metadata row goes with it. (Soft
    delete via products.is_active is the normal path; CASCADE only
    fires on a real DELETE.)
  * Foreign key uploaded_by_user_id → users.id, ON DELETE RESTRICT —
    the uploader is required, so we prevent removing a user while
    they still own image metadata. Matches the NOT NULL contract;
    SET NULL would violate it and CASCADE would silently delete the
    image record on user removal, which is a worse default.
  * UNIQUE (product_id) — enforces "one primary image per product"
    from the F2.22.4 scope lock. The unique constraint creates an
    implicit btree index, so per-product lookups stay indexed (the
    same pattern product_variants(sku) uses — see migration
    7a5ba742b190).
  * Index ix_product_images_uploaded_by_user_id on the uploader FK,
    matching the project convention for FK columns
    (cf. ix_product_compliance_audit_logs_changed_by_user_id).
  * No CHECK on object_key beyond NOT NULL: the upload service (a
    later subphase) is responsible for object-key formatting and
    safety. Pushing key-format rules into a DB CHECK would couple
    the schema to a particular path convention.
  * A row-level `set_updated_at` trigger keeps updated_at fresh on
    UPDATE, matching the pattern every other timestamped table in
    this schema uses (function created in the initial migration).

Out of scope (deferred or banned):
  * No image_url / image_path columns on `products`
    (docs/f2.22-contract-lock.md §8.1).
  * No image fields on `product_variants` (no variant images in
    F2.22.4).
  * No multi-image gallery columns.
  * No bucket column — the bucket is contractually `product-images`
    for F2.22.4. Adding a bucket column would also imply
    cross-bucket reuse, which the scope lock explicitly rejects.
  * No RLS policy on the table — F2.22.4.E adds RLS deny-all.
  * No upload endpoint, no signed URL generation, no Supabase
    Storage service — those land in F2.22.4.F.

Revision ID: d2f9e8a7c1b6
Revises: c8f1a2d3e4b5
Create Date: 2026-05-27 14:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2f9e8a7c1b6"
down_revision = "c8f1a2d3e4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_images_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name="fk_product_images_uploaded_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "product_id",
            name="uq_product_images_product_id",
        ),
    )
    op.create_index(
        "ix_product_images_uploaded_by_user_id",
        "product_images",
        ["uploaded_by_user_id"],
        unique=False,
    )

    # Keep updated_at fresh on UPDATE, matching every other
    # timestamped table in this schema. The set_updated_at() function
    # is created by migration 7a5ba742b190 (initial schema).
    op.execute(
        """
        CREATE TRIGGER trg_product_images_set_updated_at
        BEFORE UPDATE ON product_images
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_product_images_set_updated_at "
        "ON product_images"
    )
    op.drop_index(
        "ix_product_images_uploaded_by_user_id",
        table_name="product_images",
    )
    op.drop_table("product_images")

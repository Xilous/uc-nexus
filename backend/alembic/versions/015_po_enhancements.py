"""PO enhancements: nullable po_number, request_number, vendor_quote_number, po_documents

Revision ID: 015
Revises: 014
Create Date: 2026-03-18
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make po_number nullable
    op.alter_column("purchase_orders", "po_number", existing_type=sa.String(50), nullable=True)

    # 2. Drop the old global unique index on po_number
    op.drop_index("ix_purchase_orders_po_number", table_name="purchase_orders")

    # 3. Add partial unique index: (project_id, po_number) WHERE po_number IS NOT NULL
    op.execute(
        "CREATE UNIQUE INDEX ix_purchase_orders_project_po_number "
        "ON purchase_orders (project_id, po_number) "
        "WHERE po_number IS NOT NULL"
    )

    # 4. Add request_number column — backfill existing rows first
    op.add_column("purchase_orders", sa.Column("request_number", sa.String(50), nullable=True))

    # Backfill: use po_number if set, otherwise generate sequential
    op.execute(
        "UPDATE purchase_orders SET request_number = COALESCE(po_number, 'PO-REQ-' || "
        "LPAD(CAST(ROW_NUMBER() OVER (ORDER BY created_at) AS TEXT), 3, '0'))"
    )

    # Now make it NOT NULL
    op.alter_column("purchase_orders", "request_number", existing_type=sa.String(50), nullable=False)

    # Add unique index on request_number
    op.create_index("ix_purchase_orders_request_number", "purchase_orders", ["request_number"], unique=True)

    # 5. Add vendor_quote_number column
    op.add_column("purchase_orders", sa.Column("vendor_quote_number", sa.String(), nullable=True))

    # 6. Create po_document_type enum
    po_doc_type = sa.Enum("PO_DOCUMENT", "VENDOR_ACKNOWLEDGEMENT", "MISCELLANEOUS", name="po_document_type")
    po_doc_type.create(op.get_bind())

    # 7. Create po_documents table
    op.create_table(
        "po_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("po_id", sa.Uuid(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("document_type", po_doc_type, nullable=False),
        sa.Column("s3_key", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_po_documents_po_id", "po_documents", ["po_id"])


def downgrade() -> None:
    op.drop_index("ix_po_documents_po_id", table_name="po_documents")
    op.drop_table("po_documents")

    sa.Enum(name="po_document_type").drop(op.get_bind())

    op.drop_column("purchase_orders", "vendor_quote_number")

    op.drop_index("ix_purchase_orders_request_number", table_name="purchase_orders")
    op.drop_column("purchase_orders", "request_number")

    op.execute("DROP INDEX IF EXISTS ix_purchase_orders_project_po_number")

    # Re-create the old global unique index — only works if all po_numbers are non-null and unique
    op.execute("UPDATE purchase_orders SET po_number = 'MIGRATED-' || id::text WHERE po_number IS NULL")
    op.alter_column("purchase_orders", "po_number", existing_type=sa.String(50), nullable=False)
    op.create_index("ix_purchase_orders_po_number", "purchase_orders", ["po_number"], unique=True)

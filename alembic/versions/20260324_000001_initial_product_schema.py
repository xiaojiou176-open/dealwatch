"""initial product schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260324_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("default_zip_code", sa.String(length=32), nullable=False),
        sa.Column("default_check_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("default_email_recipient", sa.String(length=255), nullable=False),
        sa.Column("notification_cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "watch_targets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("store_key", sa.String(length=64), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("last_resolution_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_targets_user_id", "watch_targets", ["user_id"])
    op.create_index("ix_watch_targets_normalized_url", "watch_targets", ["normalized_url"])

    op.create_table(
        "watch_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watch_target_id", sa.String(length=36), sa.ForeignKey("watch_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False),
        sa.Column("run_mode", sa.String(length=32), nullable=False),
        sa.Column("threshold_type", sa.String(length=64), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_tasks_user_id", "watch_tasks", ["user_id"])
    op.create_index("ix_watch_tasks_watch_target_id", "watch_tasks", ["watch_target_id"])
    op.create_index("ix_watch_tasks_status", "watch_tasks", ["status"])
    op.create_index("ix_watch_tasks_next_run_at", "watch_tasks", ["next_run_at"])

    op.create_table(
        "task_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("artifact_run_dir", sa.Text(), nullable=True),
        sa.Column("engine_store_key", sa.String(length=64), nullable=True),
        sa.Column("engine_product_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_runs_watch_task_id", "task_runs", ["watch_task_id"])
    op.create_index("ix_task_runs_status", "task_runs", ["status"])

    op.create_table(
        "price_observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_run_id", sa.String(length=36), sa.ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listed_price", sa.Float(), nullable=False),
        sa.Column("original_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("availability", sa.String(length=32), nullable=False),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("unit_price_raw", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_price_observations_watch_task_id", "price_observations", ["watch_task_id"])
    op.create_index("ix_price_observations_task_run_id", "price_observations", ["task_run_id"])
    op.create_index("ix_price_observations_observed_at", "price_observations", ["observed_at"])

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_rules_watch_task_id", "notification_rules", ["watch_task_id"])

    op.create_table(
        "delivery_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_run_id", sa.String(length=36), sa.ForeignKey("task_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payload_json", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_delivery_events_watch_task_id", "delivery_events", ["watch_task_id"])
    op.create_index("ix_delivery_events_task_run_id", "delivery_events", ["task_run_id"])
    op.create_index("ix_delivery_events_status", "delivery_events", ["status"])

    op.create_table(
        "store_adapter_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("store_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("adapter_class", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_store_adapter_bindings_store_key", "store_adapter_bindings", ["store_key"], unique=True)

    op.create_table(
        "cashback_quotes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("merchant_key", sa.String(length=128), nullable=False),
        sa.Column("rate_type", sa.String(length=32), nullable=False),
        sa.Column("rate_value", sa.Float(), nullable=False),
        sa.Column("conditions_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cashback_quotes_watch_task_id", "cashback_quotes", ["watch_task_id"])

    op.create_table(
        "effective_price_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_run_id", sa.String(length=36), sa.ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listed_price", sa.Float(), nullable=False),
        sa.Column("cashback_amount", sa.Float(), nullable=False),
        sa.Column("effective_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_effective_price_snapshots_watch_task_id", "effective_price_snapshots", ["watch_task_id"])
    op.create_index("ix_effective_price_snapshots_task_run_id", "effective_price_snapshots", ["task_run_id"])

    op.create_table(
        "canonical_products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("size_hint", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "product_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("canonical_product_id", sa.String(length=36), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watch_task_id", sa.String(length=36), sa.ForeignKey("watch_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("merchant_key", sa.String(length=128), nullable=False),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
    )
    op.create_index("ix_product_candidates_canonical_product_id", "product_candidates", ["canonical_product_id"])
    op.create_index("ix_product_candidates_watch_task_id", "product_candidates", ["watch_task_id"])


def downgrade() -> None:
    op.drop_index("ix_product_candidates_watch_task_id", table_name="product_candidates")
    op.drop_index("ix_product_candidates_canonical_product_id", table_name="product_candidates")
    op.drop_table("product_candidates")
    op.drop_table("canonical_products")
    op.drop_index("ix_effective_price_snapshots_task_run_id", table_name="effective_price_snapshots")
    op.drop_index("ix_effective_price_snapshots_watch_task_id", table_name="effective_price_snapshots")
    op.drop_table("effective_price_snapshots")
    op.drop_index("ix_cashback_quotes_watch_task_id", table_name="cashback_quotes")
    op.drop_table("cashback_quotes")
    op.drop_index("ix_store_adapter_bindings_store_key", table_name="store_adapter_bindings")
    op.drop_table("store_adapter_bindings")
    op.drop_index("ix_delivery_events_status", table_name="delivery_events")
    op.drop_index("ix_delivery_events_task_run_id", table_name="delivery_events")
    op.drop_index("ix_delivery_events_watch_task_id", table_name="delivery_events")
    op.drop_table("delivery_events")
    op.drop_index("ix_notification_rules_watch_task_id", table_name="notification_rules")
    op.drop_table("notification_rules")
    op.drop_index("ix_price_observations_observed_at", table_name="price_observations")
    op.drop_index("ix_price_observations_task_run_id", table_name="price_observations")
    op.drop_index("ix_price_observations_watch_task_id", table_name="price_observations")
    op.drop_table("price_observations")
    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_index("ix_task_runs_watch_task_id", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_index("ix_watch_tasks_next_run_at", table_name="watch_tasks")
    op.drop_index("ix_watch_tasks_status", table_name="watch_tasks")
    op.drop_index("ix_watch_tasks_watch_target_id", table_name="watch_tasks")
    op.drop_index("ix_watch_tasks_user_id", table_name="watch_tasks")
    op.drop_table("watch_tasks")
    op.drop_index("ix_watch_targets_normalized_url", table_name="watch_targets")
    op.drop_index("ix_watch_targets_user_id", table_name="watch_targets")
    op.drop_table("watch_targets")
    op.drop_table("user_preferences")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

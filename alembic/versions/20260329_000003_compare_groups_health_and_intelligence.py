"""compare groups, health, and intelligence"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_000003"
down_revision = "20260328_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("watch_tasks", sa.Column("health_status", sa.String(length=32), nullable=False, server_default="healthy"))
    op.add_column("watch_tasks", sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("watch_tasks", sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("watch_tasks", sa.Column("last_failure_kind", sa.String(length=64), nullable=True))
    op.add_column("watch_tasks", sa.Column("manual_intervention_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_watch_tasks_health_status", "watch_tasks", ["health_status"])

    op.create_table(
        "watch_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("zip_code", sa.String(length=32), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False),
        sa.Column("threshold_type", sa.String(length=64), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_kind", sa.String(length=64), nullable=True),
        sa.Column("manual_intervention_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_groups_user_id", "watch_groups", ["user_id"])
    op.create_index("ix_watch_groups_status", "watch_groups", ["status"])
    op.create_index("ix_watch_groups_next_run_at", "watch_groups", ["next_run_at"])
    op.create_index("ix_watch_groups_health_status", "watch_groups", ["health_status"])

    op.create_table(
        "watch_group_members",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_group_id", sa.String(length=36), sa.ForeignKey("watch_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watch_target_id", sa.String(length=36), sa.ForeignKey("watch_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("candidate_key", sa.Text(), nullable=False),
        sa.Column("brand_hint", sa.String(length=255), nullable=True),
        sa.Column("size_hint", sa.String(length=255), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_group_members_watch_group_id", "watch_group_members", ["watch_group_id"])
    op.create_index("ix_watch_group_members_watch_target_id", "watch_group_members", ["watch_target_id"])

    op.create_table(
        "watch_group_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watch_group_id", sa.String(length=36), sa.ForeignKey("watch_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("artifact_run_dir", sa.Text(), nullable=True),
        sa.Column("winner_member_id", sa.String(length=36), sa.ForeignKey("watch_group_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("winner_effective_price", sa.Float(), nullable=True),
        sa.Column("runner_up_member_id", sa.String(length=36), sa.ForeignKey("watch_group_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("runner_up_effective_price", sa.Float(), nullable=True),
        sa.Column("price_spread", sa.Float(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("member_results_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_group_runs_watch_group_id", "watch_group_runs", ["watch_group_id"])
    op.create_index("ix_watch_group_runs_status", "watch_group_runs", ["status"])
    op.create_index("ix_watch_group_runs_winner_member_id", "watch_group_runs", ["winner_member_id"])
    op.create_index("ix_watch_group_runs_runner_up_member_id", "watch_group_runs", ["runner_up_member_id"])

    op.alter_column("delivery_events", "watch_task_id", existing_type=sa.String(length=36), nullable=True)
    op.add_column("delivery_events", sa.Column("watch_group_id", sa.String(length=36), nullable=True))
    op.add_column("delivery_events", sa.Column("watch_group_run_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_delivery_events_watch_group_id_watch_groups", "delivery_events", "watch_groups", ["watch_group_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_delivery_events_watch_group_run_id_watch_group_runs", "delivery_events", "watch_group_runs", ["watch_group_run_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(
        "ck_delivery_events_owner_ref",
        "delivery_events",
        "watch_task_id IS NOT NULL OR watch_group_id IS NOT NULL",
    )
    op.create_index("ix_delivery_events_watch_group_id", "delivery_events", ["watch_group_id"])
    op.create_index("ix_delivery_events_watch_group_run_id", "delivery_events", ["watch_group_run_id"])

    op.add_column("effective_price_snapshots", sa.Column("previous_listed_price", sa.Float(), nullable=True))
    op.add_column("effective_price_snapshots", sa.Column("delta_amount", sa.Float(), nullable=True))
    op.add_column("effective_price_snapshots", sa.Column("delta_pct", sa.Float(), nullable=True))
    op.add_column("effective_price_snapshots", sa.Column("is_new_low", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("effective_price_snapshots", sa.Column("anomaly_reason", sa.String(length=32), nullable=True))
    op.add_column("effective_price_snapshots", sa.Column("decision_reason", sa.Text(), nullable=True))

    op.execute("UPDATE watch_tasks SET health_status = 'healthy' WHERE health_status IS NULL")
    op.execute("UPDATE watch_tasks SET consecutive_failures = 0 WHERE consecutive_failures IS NULL")
    op.execute("UPDATE watch_tasks SET manual_intervention_required = false WHERE manual_intervention_required IS NULL")

    op.alter_column("watch_tasks", "health_status", server_default=None)
    op.alter_column("watch_tasks", "consecutive_failures", server_default=None)
    op.alter_column("watch_tasks", "manual_intervention_required", server_default=None)
    op.alter_column("effective_price_snapshots", "is_new_low", server_default=None)


def downgrade() -> None:
    op.drop_column("effective_price_snapshots", "decision_reason")
    op.drop_column("effective_price_snapshots", "anomaly_reason")
    op.drop_column("effective_price_snapshots", "is_new_low")
    op.drop_column("effective_price_snapshots", "delta_pct")
    op.drop_column("effective_price_snapshots", "delta_amount")
    op.drop_column("effective_price_snapshots", "previous_listed_price")

    op.drop_index("ix_delivery_events_watch_group_run_id", table_name="delivery_events")
    op.drop_index("ix_delivery_events_watch_group_id", table_name="delivery_events")
    op.drop_constraint("ck_delivery_events_owner_ref", "delivery_events", type_="check")
    op.drop_constraint("fk_delivery_events_watch_group_run_id_watch_group_runs", "delivery_events", type_="foreignkey")
    op.drop_constraint("fk_delivery_events_watch_group_id_watch_groups", "delivery_events", type_="foreignkey")
    op.drop_column("delivery_events", "watch_group_run_id")
    op.drop_column("delivery_events", "watch_group_id")
    op.alter_column("delivery_events", "watch_task_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_index("ix_watch_group_runs_runner_up_member_id", table_name="watch_group_runs")
    op.drop_index("ix_watch_group_runs_winner_member_id", table_name="watch_group_runs")
    op.drop_index("ix_watch_group_runs_status", table_name="watch_group_runs")
    op.drop_index("ix_watch_group_runs_watch_group_id", table_name="watch_group_runs")
    op.drop_table("watch_group_runs")

    op.drop_index("ix_watch_group_members_watch_target_id", table_name="watch_group_members")
    op.drop_index("ix_watch_group_members_watch_group_id", table_name="watch_group_members")
    op.drop_table("watch_group_members")

    op.drop_index("ix_watch_groups_health_status", table_name="watch_groups")
    op.drop_index("ix_watch_groups_next_run_at", table_name="watch_groups")
    op.drop_index("ix_watch_groups_status", table_name="watch_groups")
    op.drop_index("ix_watch_groups_user_id", table_name="watch_groups")
    op.drop_table("watch_groups")

    op.drop_index("ix_watch_tasks_health_status", table_name="watch_tasks")
    op.drop_column("watch_tasks", "manual_intervention_required")
    op.drop_column("watch_tasks", "last_failure_kind")
    op.drop_column("watch_tasks", "backoff_until")
    op.drop_column("watch_tasks", "consecutive_failures")
    op.drop_column("watch_tasks", "health_status")

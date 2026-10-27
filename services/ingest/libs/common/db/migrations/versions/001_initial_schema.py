"""Initial schema migration creating all M1 tables.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-27 22:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. runs
    op.create_table(
        'runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('route', sa.String(length=64), nullable=True),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prompt_versions_json', sa.JSON(), nullable=True),
        sa.Column('index_version', sa.String(length=64), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tokens_prompt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_completion', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('degraded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('worker_id', sa.String(length=128), nullable=True),
        sa.Column('task_id', sa.String(length=128), nullable=True),
    )
    op.create_index('idx_runs_run_id', 'runs', ['run_id'])
    op.create_index('idx_runs_correlation_id', 'runs', ['correlation_id'])
    op.create_index('idx_runs_client_id', 'runs', ['client_id'])
    op.create_index('idx_runs_status', 'runs', ['status'])
    op.create_index('idx_runs_route', 'runs', ['route'])
    op.create_index('idx_runs_created_at', 'runs', ['created_at'])
    op.create_index('idx_runs_client_status', 'runs', ['client_id', 'status'])

    # 2. run_steps
    op.create_table(
        'run_steps',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_name', sa.String(length=64), nullable=False),
        sa.Column('agent', sa.String(length=64), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('tokens_prompt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_completion', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tool_calls_json', sa.JSON(), nullable=True),
        sa.Column('retrieved_passage_ids', sa.JSON(), nullable=True),
        sa.Column('prompt_version', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='SUCCESS'),
        sa.Column('error', sa.Text(), nullable=True),
    )
    op.create_index('idx_run_steps_run_id', 'run_steps', ['run_id'])
    op.create_index('idx_run_steps_run_agent', 'run_steps', ['run_id', 'agent'])

    # 3. quarantine
    op.create_table(
        'quarantine',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('raw_payload_json', sa.JSON(), nullable=False),
        sa.Column('field_errors_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('client_ip', sa.String(length=64), nullable=True),
    )
    op.create_index('idx_quarantine_correlation_id', 'quarantine', ['correlation_id'])
    op.create_index('idx_quarantine_created_at', 'quarantine', ['created_at'])

    # 4. clause_index
    op.create_table(
        'clause_index',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('identifier', sa.String(length=64), nullable=False),
        sa.Column('chunk_ids_json', sa.JSON(), nullable=False),
        sa.Column('doc_id', sa.String(length=64), nullable=False),
        sa.Column('doc_title', sa.String(length=255), nullable=False),
        sa.Column('clause_ref', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('index_version', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_clause_identifier', 'clause_index', ['identifier'])
    op.create_index('idx_clause_doc_id', 'clause_index', ['doc_id'])
    op.create_index('idx_clause_id_version', 'clause_index', ['identifier', 'index_version'])

    # 5. cross_ref_index
    op.create_table(
        'cross_ref_index',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('source_chunk_id', sa.String(length=64), nullable=False),
        sa.Column('target_chunk_id', sa.String(length=64), nullable=False),
        sa.Column('ref_type', sa.String(length=64), nullable=False),
        sa.Column('ref_text', sa.Text(), nullable=False),
        sa.Column('index_version', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_cross_ref_source', 'cross_ref_index', ['source_chunk_id'])
    op.create_index('idx_cross_ref_target', 'cross_ref_index', ['target_chunk_id'])
    op.create_index('idx_cross_ref_source_target', 'cross_ref_index', ['source_chunk_id', 'target_chunk_id'])

    # 6. index_manifest
    op.create_table(
        'index_manifest',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('built_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doc_count', sa.Integer(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('embedding_model', sa.String(length=128), nullable=False),
        sa.Column('embedding_version', sa.String(length=64), nullable=False),
        sa.Column('index_version', sa.String(length=64), unique=True, nullable=False),
        sa.Column('throughput_chunks_per_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('source_hashes_json', sa.JSON(), nullable=False),
    )
    op.create_index('idx_manifest_version', 'index_manifest', ['index_version'])

    # 7. feedback
    op.create_table(
        'feedback',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('satisfactory', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_feedback_run_id', 'feedback', ['run_id'])

    # 8. eval_results
    op.create_table(
        'eval_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), nullable=True),
        sa.Column('scenario_id', sa.String(length=128), nullable=False),
        sa.Column('prompt_variant', sa.String(length=64), nullable=False),
        sa.Column('groundedness', sa.Float(), nullable=True),
        sa.Column('context_relevance', sa.Float(), nullable=True),
        sa.Column('faithfulness', sa.Float(), nullable=True),
        sa.Column('hallucination_rate', sa.Float(), nullable=True),
        sa.Column('route_correct', sa.Boolean(), nullable=True),
        sa.Column('citation_recall', sa.Float(), nullable=True),
        sa.Column('is_correct_escalation', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scored_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_eval_scenario_id', 'eval_results', ['scenario_id'])
    op.create_index('idx_eval_run_id', 'eval_results', ['run_id'])


def downgrade() -> None:
    op.drop_table('eval_results')
    op.drop_table('feedback')
    op.drop_table('index_manifest')
    op.drop_table('cross_ref_index')
    op.drop_table('clause_index')
    op.drop_table('quarantine')
    op.drop_table('run_steps')
    op.drop_table('runs')

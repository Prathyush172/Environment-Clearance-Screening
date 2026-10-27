"""CLI entrypoint for EIA corpus ingestion and index management."""

import asyncio
import click
from sqlalchemy import select, desc
from libs.common.db.session import get_db_session
from libs.common.db.models import IndexManifest, ClauseIndex
from services.ingest.pipeline import run_pipeline


@click.group()
def cli():
    """EIA Notification Corpus Ingest & Index CLI."""
    pass


@cli.command()
@click.option("--corpus", default="/data/corpus", help="Corpus directory containing EIA PDFs")
@click.option("--reembed", is_flag=True, help="Re-embed all chunks")
@click.option("--only", default=None, help="Only process specific doc_id or filename")
@click.option("--dry-run", is_flag=True, help="Dry run, no writes to Chroma or DB")
def run(corpus, reembed, only, dry_run):
    """Run ingestion pipeline over PDF corpus."""
    click.echo(f"Starting ingestion on {corpus} (dry_run={dry_run})...")
    res = asyncio.run(run_pipeline(corpus_dir=corpus, reembed=reembed, only=only, dry_run=dry_run))
    click.echo(f"Ingestion result: {res}")


@cli.command()
def status():
    """Check index status and manifest information."""
    async def _status():
        async with get_db_session() as session:
            manifest_q = (
                select(IndexManifest)
                .order_by(desc(IndexManifest.built_at))
                .limit(1)
            )
            res = await session.execute(manifest_q)
            latest = res.scalar_one_or_none()

            if not latest:
                click.echo("No index manifest found. Ingestion has not run yet.")
                return

            click.echo(f"Active Index Version: {latest.index_version}")
            click.echo(f"Built At: {latest.built_at}")
            click.echo(f"Document Count: {latest.doc_count}")
            click.echo(f"Chunk Count: {latest.chunk_count}")
            click.echo(f"Embedding Model: {latest.embedding_model}")
            click.echo(f"Throughput: {latest.throughput_chunks_per_sec} chunks/sec")

    asyncio.run(_status())


if __name__ == "__main__":
    cli()

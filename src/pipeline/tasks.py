from arq import ArqRedis

from src.pipeline.stages import run_pipeline


async def process_document(ctx: dict, processing_id: str) -> None:
    """ARQ task entry point. Called by intake after successful upload."""
    await run_pipeline(processing_id)

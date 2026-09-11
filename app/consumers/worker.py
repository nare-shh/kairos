"""
Kairos Event Worker
═══════════════════
A Kafka consumer process that runs alongside the API:

    python -m app.consumers.worker

The API publishes every intent event to `kairos.intent.events`.
This worker consumes that stream and maintains the real-time trending
leaderboard in Redis (served by GET /api/v1/products/trending).

Why a separate process? Consumers scale independently of the API,
and a slow consumer can never slow down a user's request.
"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.consumers.trending import apply_intent_event
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.redis import close_redis, get_redis, init_redis
from app.events.publisher import KafkaTopic

logger = logging.getLogger("kairos.worker")

CONSUMER_GROUP = "kairos-trending"
STARTUP_RETRIES = 30
RETRY_DELAY_SECONDS = 2


async def _start_consumer() -> AIOKafkaConsumer:
    """Kafka can take a while to boot in docker-compose — retry instead of crashing."""
    for attempt in range(1, STARTUP_RETRIES + 1):
        consumer = AIOKafkaConsumer(
            KafkaTopic.INTENT_EVENTS,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        try:
            await consumer.start()
            return consumer
        except (KafkaConnectionError, OSError) as e:
            await consumer.stop()
            logger.warning(f"Kafka not reachable (attempt {attempt}/{STARTUP_RETRIES}): {e}")
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Could not connect to Kafka at {settings.KAFKA_BOOTSTRAP_SERVERS}")


async def run() -> None:
    setup_logging()
    if not settings.KAFKA_ENABLED:
        logger.warning("KAFKA_ENABLED=false — nothing to consume, worker exiting")
        return

    await init_redis()
    consumer = await _start_consumer()
    logger.info(f"Worker consuming {KafkaTopic.INTENT_EVENTS} as group '{CONSUMER_GROUP}'")

    try:
        async for record in consumer:
            try:
                await apply_intent_event(get_redis(), record.value)
            except Exception:
                # One poison message must not stop the stream
                logger.exception(f"Failed to process record at offset {record.offset}")
    finally:
        await consumer.stop()
        await close_redis()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

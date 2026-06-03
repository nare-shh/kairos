import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — one producer shared across all requests
# Creating a new producer per request would be extremely wasteful
_producer: AIOKafkaProducer | None = None


# ── Kafka Topic Names ──────────────────────────────────────────────────────────
# Topics are like "channels" in Kafka — messages are published to topics,
# consumers subscribe to topics.
# Convention: use dot-separated names, lowercase
class KafkaTopic:
    PRODUCT_EVENTS = "kairos.product.events"
    ORDER_EVENTS = "kairos.order.events"
    INTENT_EVENTS = "kairos.intent.events"      # User behavior → pricing engine
    PRICING_COMMANDS = "kairos.pricing.commands"


async def init_kafka_producer() -> None:
    """
    Called once at app startup.
    Creates a connection pool to Kafka brokers.
    """
    global _producer
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            # value_serializer converts Python dicts → bytes before sending
            # We serialize to JSON then encode to bytes
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            # key_serializer converts the partition key → bytes
            # We use aggregate_id as the key so all events for the same entity
            # go to the SAME Kafka partition → guaranteed ordering per entity
            key_serializer=lambda v: v.encode("utf-8") if v else None,
            # acks="all" → wait for ALL replicas to confirm before considering sent
            # This prevents data loss if the leader broker crashes
            acks="all",
            # retry_backoff_ms → wait 100ms between retries (don't hammer the broker)
            retry_backoff_ms=100,
        )
        await _producer.start()
        logger.info("Kafka producer connected")
    except KafkaConnectionError as e:
        # In development, Kafka might not be ready yet — log but don't crash
        # The app can still work; events just won't be published
        logger.warning(f"Kafka not available: {e}. Events will be stored but not streamed.")
        _producer = None


async def close_kafka_producer() -> None:
    """Called at app shutdown to flush remaining messages and close connection."""
    global _producer
    if _producer:
        await _producer.stop()
        logger.info("Kafka producer closed")


async def publish_event(
    topic: str,
    event_type: str,
    aggregate_id: str,
    payload: dict,
    caused_by: str | None = None,
) -> None:
    """
    Publish an event to a Kafka topic.

    Parameters:
        topic        → which Kafka topic to publish to
        event_type   → e.g. "ProductCreated", "ProductPriceChanged"
        aggregate_id → the ID of the entity this event is about
                       (used as partition key → ordering guarantee)
        payload      → the event data
        caused_by    → user ID who triggered this event

    The message sent to Kafka looks like:
    {
        "event_type": "ProductCreated",
        "aggregate_id": "abc-123",
        "payload": { ... },
        "occurred_at": "2025-01-01T00:00:00Z",
        "caused_by": "user-uuid"
    }

    Consumers (pricing engine, fraud detector, etc.) receive this and act on it.
    """
    if _producer is None:
        # Kafka not available — log and skip (graceful degradation)
        # The event is still saved to event_store in the DB, just not streamed
        logger.warning(f"Kafka unavailable — event {event_type} not streamed (saved to DB)")
        return

    message = {
        "event_type": event_type,
        "aggregate_id": aggregate_id,
        "payload": payload,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "caused_by": caused_by,
    }

    try:
        await _producer.send_and_wait(
            topic=topic,
            value=message,
            key=aggregate_id,   # partition key = same product always → same partition → ordered
        )
        logger.debug(f"Published {event_type} for {aggregate_id} to {topic}")
    except Exception as e:
        # Publishing failure should NOT fail the user's request
        # The event is already saved to the DB — that's the source of truth
        # Kafka is for real-time streaming, not persistence
        logger.error(f"Failed to publish {event_type} to Kafka: {e}")

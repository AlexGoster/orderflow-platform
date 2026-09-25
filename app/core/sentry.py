import logging

logger = logging.getLogger(__name__)


def init_sentry(dsn: str, *, environment: str, release: str, traces_sample_rate: float) -> None:
    """Подключает Sentry только если задан SENTRY_DSN (интеграция env-based)."""
    if not dsn:
        logger.info("sentry disabled: SENTRY_DSN is empty")
        return

    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        integrations=[sentry_logging],
    )
    logger.info("sentry initialized", extra={"environment": environment})

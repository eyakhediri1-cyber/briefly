"""Job platform integrations — real API sources only."""

from app.services.integrations.remoteok import RemoteOKIntegration
from app.services.integrations.remotive import RemotiveIntegration
from app.services.integrations.arbeitnow import ArbeitnowIntegration
from app.services.integrations.aiesec import AIESECIntegration

# Default enabled sources (see ENABLED_JOB_SOURCES in config)
ALL_INTEGRATIONS = [
    RemoteOKIntegration,
    RemotiveIntegration,
    ArbeitnowIntegration,
    AIESECIntegration,
]

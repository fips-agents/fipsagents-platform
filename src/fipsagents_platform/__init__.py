"""Cross-agent platform service for fips-agents.

Centralizes feedback, sessions, and traces over REST so a multi-agent
deployment runs against one Postgres pool, one schema, one auth boundary.

Architecture: see fips-agents/agent-template#112.
"""

__version__ = "0.1.0"

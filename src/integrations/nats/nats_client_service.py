from collections.abc import Awaitable, Callable
from typing import Any
import ssl

from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrNoServers, ErrTimeout
from nats.aio.msg import Msg

from core.log import get_logger
from integrations.nats.config import NatsConfig

MessageHandler = Callable[[Msg], Awaitable[None]]


class NatsClientService:
    """Service for managing NATS client connections and message handling."""

    def __init__(self, nats_config: NatsConfig):
        """Initialize NATS client service.

        Args:
            nats_config: NATS configuration instance
        """
        self.log = get_logger(logger_name="NatsClientService", level="INFO")
        self.config = nats_config
        self.nc: NATS | None = None

        # Validate configuration
        if not self.config.is_configured():
            raise ValueError("NATS configuration is incomplete")

    def _create_tls_context(self) -> ssl.SSLContext | None:
        """Create TLS context for secure NATS connection."""
        ca_cert_path = self.config.get_ca_cert_path()
        if not ca_cert_path:
            return None

        ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        ctx.load_verify_locations(cafile=ca_cert_path)
        ctx.check_hostname = True
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    async def connect(self) -> None:
        """Establish connection to NATS server."""
        server_url = self.config.get_server_url()
        user = self.config.get_user()
        password = self.config.get_password()

        if not server_url:
            raise ValueError("NATS server URL is not configured")

        self.nc = NATS()

        try:
            connect_options: dict[str, Any] = {
                "servers": [server_url],
                "allow_reconnect": True,
                "reconnect_time_wait": 2,
                "max_reconnect_attempts": -1,
                "name": "dev-agents-worker",
            }

            if user and password:
                connect_options["user"] = user
                connect_options["password"] = password

            tls_context = self._create_tls_context()
            if tls_context:
                connect_options["tls"] = tls_context

            await self.nc.connect(**connect_options)
            self.log.info(f"Connected to NATS server at {server_url}")

        except (ErrConnectionClosed, ErrTimeout, ErrNoServers) as e:
            self.log.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Gracefully disconnect from NATS server."""
        if self.nc and self.nc.is_connected:
            try:
                await self.nc.drain()
                self.log.info("Disconnected from NATS server")
            except Exception as e:
                self.log.error(f"Error during NATS disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if client is connected to NATS server."""
        return self.nc is not None and self.nc.is_connected

    async def subscribe(self, subject: str, cb: MessageHandler) -> None:
        """Subscribe to a NATS subject.

        The callback receives the raw :class:`nats.aio.msg.Msg`. Parsing,
        dispatching and reply logic are the caller's responsibility — the
        client only carries bytes.

        Args:
            subject: NATS subject (supports wildcards ``*`` / ``>``)
            cb: Async handler invoked for each received message
        """
        if not self.nc or not self.nc.is_connected:
            raise RuntimeError("Not connected to NATS server")

        await self.nc.subscribe(subject, cb=cb)
        self.log.info(f"Subscribed to NATS subject: {subject}")

    async def publish(self, subject: str, message: str) -> None:
        """Publish a message to a NATS subject."""
        if not self.nc or not self.nc.is_connected:
            raise RuntimeError("Not connected to NATS server")

        try:
            await self.nc.publish(subject, message.encode())
            self.log.debug(f"Published message to {subject}: {message}")
        except Exception as e:
            self.log.error(f"Failed to publish message: {e}")
            raise

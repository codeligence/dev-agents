from collections.abc import Callable
from typing import Any
import json
import ssl

from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrNoServers, ErrTimeout
from nats.aio.msg import Msg

from core.log import get_logger
from integrations.nats.config import NatsConfig
from integrations.nats.models import NatsJob


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
        self.message_callback: Callable[[NatsJob], None] | None = None

        # Validate configuration
        if not self.config.is_configured():
            raise ValueError("NATS configuration is incomplete")

    def _create_tls_context(self) -> ssl.SSLContext | None:
        """Create TLS context for secure NATS connection.

        Returns:
            SSL context if CA cert path is configured, None otherwise
        """
        ca_cert_path = self.config.get_ca_cert_path()
        if not ca_cert_path:
            return None

        ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        # Trust the server certificate
        ctx.load_verify_locations(cafile=ca_cert_path)
        # Hostname verification is enabled by default
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
            # Prepare connection options
            connect_options: dict[str, Any] = {
                "servers": [server_url],
                "allow_reconnect": True,
                "reconnect_time_wait": 2,
                "max_reconnect_attempts": -1,
                "name": "dev-agents-worker",
            }

            # Add authentication if configured
            if user and password:
                connect_options["user"] = user
                connect_options["password"] = password

            # Add TLS context if CA cert is configured
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
        """Check if client is connected to NATS server.

        Returns:
            True if connected, False otherwise
        """
        return self.nc is not None and self.nc.is_connected

    async def subscribe(self, subject: str) -> None:
        """Subscribe to a NATS subject.

        Args:
            subject: NATS subject to subscribe to
        """
        if not self.nc or not self.nc.is_connected:
            raise RuntimeError("Not connected to NATS server")

        async def message_handler(msg: Msg) -> None:
            """Handle incoming NATS messages."""
            try:
                data = msg.data.decode()
                self.log.debug(f"Received message on {msg.subject}: {data}")

                # Parse JSON message to NatsJob
                job_data = json.loads(data)
                job = NatsJob(
                    id=job_data["id"],
                    project=job_data["project"],
                    prompt=job_data["prompt"],
                )

                # Call registered callback if available
                if self.message_callback:
                    self.message_callback(job)

            except json.JSONDecodeError as e:
                self.log.error(f"Failed to parse JSON message: {e}")
            except KeyError as e:
                self.log.error(f"Missing required field in job message: {e}")
            except Exception as e:
                self.log.error(f"Error handling message: {e}")

        await self.nc.subscribe(subject, cb=message_handler)
        self.log.info(f"Subscribed to NATS subject: {subject}")

    async def publish(self, subject: str, message: str) -> None:
        """Publish a message to a NATS subject.

        Args:
            subject: NATS subject to publish to
            message: Message content to publish
        """
        if not self.nc or not self.nc.is_connected:
            raise RuntimeError("Not connected to NATS server")

        try:
            await self.nc.publish(subject, message.encode())
            self.log.debug(f"Published message to {subject}: {message}")
        except Exception as e:
            self.log.error(f"Failed to publish message: {e}")
            raise

    def set_message_callback(self, callback: Callable[[NatsJob], None]) -> None:
        """Set callback function for handling incoming messages.

        Args:
            callback: Function to call when a message is received
        """
        self.message_callback = callback

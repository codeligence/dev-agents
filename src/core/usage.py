"""Usage tracking service for persisting model usage statistics."""

from datetime import date, timedelta
import threading

from pydantic import BaseModel
from pydantic_ai.usage import RunUsage

from core.log import get_logger
from core.storage import BaseStorage, get_storage

logger = get_logger(__name__)


class ModelUsage(BaseModel):
    """Usage statistics for a single model.

    Mirrors the fields from pydantic_ai.RunUsage for JSON serialization.
    """

    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    input_audio_tokens: int = 0
    cache_audio_read_tokens: int = 0
    output_audio_tokens: int = 0

    def incr(self, other: "ModelUsage") -> None:
        """Add all fields from another ModelUsage in-place.

        Args:
            other: ModelUsage instance to add
        """
        self.requests += other.requests
        self.tool_calls += other.tool_calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.input_audio_tokens += other.input_audio_tokens
        self.cache_audio_read_tokens += other.cache_audio_read_tokens
        self.output_audio_tokens += other.output_audio_tokens

    @classmethod
    def from_run_usage(cls, usage: RunUsage) -> "ModelUsage":
        """Convert from pydantic_ai.RunUsage.

        Args:
            usage: RunUsage instance from pydantic_ai

        Returns:
            ModelUsage with copied fields
        """
        return cls(
            requests=usage.requests,
            tool_calls=usage.tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            input_audio_tokens=usage.input_audio_tokens,
            cache_audio_read_tokens=usage.cache_audio_read_tokens,
            output_audio_tokens=getattr(usage, "output_audio_tokens", 0),
        )


# Type aliases for clarity
DailyUsage = dict[str, ModelUsage]  # model_name -> ModelUsage
MonthlyUsage = dict[str, DailyUsage]  # date_str -> DailyUsage


class UsageStorage:
    """Usage tracking service wrapping BaseStorage.

    Provides thread-safe persistence of usage statistics organized by month.
    Each month is stored as a separate key in the underlying storage.
    """

    def __init__(self, storage: BaseStorage):
        """Initialize UsageStorage.

        Args:
            storage: BaseStorage instance to use for persistence
        """
        self._storage = storage
        self._lock = threading.Lock()

    def _get_month_key(self, d: date) -> str:
        """Get storage key for a month.

        Args:
            d: Date to get month key for

        Returns:
            Storage key in format 'usage_YYYY-MM'
        """
        return f"usage_{d.strftime('%Y-%m')}"

    def track(self, model: str, usage: RunUsage) -> None:
        """Thread-safe persist usage to storage.

        Increments the usage for the given model on today's date.

        Args:
            model: Model name/identifier
            usage: RunUsage instance with usage statistics
        """
        today = date.today()
        month_key = self._get_month_key(today)
        date_str = today.isoformat()

        with self._lock:
            monthly_data: dict[str, dict[str, dict[str, int]]] = self._storage.get(
                month_key, {}
            )

            if date_str not in monthly_data:
                monthly_data[date_str] = {}

            if model not in monthly_data[date_str]:
                monthly_data[date_str][model] = ModelUsage().model_dump()

            # Increment usage
            existing = ModelUsage(**monthly_data[date_str][model])
            existing.incr(ModelUsage.from_run_usage(usage))
            monthly_data[date_str][model] = existing.model_dump()

            self._storage.set(month_key, monthly_data)

        logger.debug(f"Tracked usage for {model} with key {month_key}")

    def load_usage(self, days: int) -> dict[str, DailyUsage]:
        """Load usage data for a date range.

        Args:
            days: Number of days to load (including today)

        Returns:
            Dict mapping date strings to daily usage
        """
        result: dict[str, DailyUsage] = {}
        today = date.today()

        # Collect all months we need to query
        months_to_query: set[str] = set()
        for i in range(days):
            d = today - timedelta(days=i)
            months_to_query.add(self._get_month_key(d))

        # Load data from each month
        for month_key in months_to_query:
            monthly_data: dict[str, dict[str, dict[str, int]]] = self._storage.get(
                month_key, {}
            )

            for date_str, models_data in monthly_data.items():
                # Check if date is within range
                try:
                    d = date.fromisoformat(date_str)
                    if (today - d).days < days:
                        # Convert to ModelUsage objects
                        daily: DailyUsage = {}
                        for model_name, usage_dict in models_data.items():
                            daily[model_name] = ModelUsage(**usage_dict)
                        result[date_str] = daily
                except ValueError:
                    continue

        return result

    def format_usage(self, usages: dict[str, DailyUsage]) -> str:
        """Create compact markdown report grouped by date with totals.

        Args:
            usages: Dict mapping date strings to daily usage

        Returns:
            Formatted compact markdown string
        """
        if not usages:
            return "No usage data available."

        def fmt_tokens(n: int) -> str:
            """Format token count compactly (e.g., 12500 -> '12.5k')."""
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            elif n >= 1_000:
                return f"{n / 1_000:.1f}k"
            return str(n)

        lines: list[str] = []
        sorted_dates = sorted(usages.keys(), reverse=True)
        model_totals: dict[str, ModelUsage] = {}
        grand_total = ModelUsage()

        for date_str in sorted_dates:
            daily = usages[date_str]
            lines.append(f"## {date_str}")

            for model_name in sorted(daily.keys()):
                usage = daily[model_name]
                lines.append(
                    f"- {model_name}: {usage.requests} req, "
                    f"{fmt_tokens(usage.input_tokens)} in, "
                    f"{fmt_tokens(usage.output_tokens)} out"
                )
                # Track per-model totals
                if model_name not in model_totals:
                    model_totals[model_name] = ModelUsage()
                model_totals[model_name].incr(usage)
                grand_total.incr(usage)

            lines.append("")

        lines.append("---")

        # Per-model totals
        for model_name in sorted(model_totals.keys()):
            usage = model_totals[model_name]
            lines.append(
                f"**{model_name}**: {usage.requests} req, "
                f"{fmt_tokens(usage.input_tokens)} in, "
                f"{fmt_tokens(usage.output_tokens)} out"
            )

        lines.append("")
        lines.append(
            f"**Total**: {grand_total.requests} req, "
            f"{fmt_tokens(grand_total.input_tokens)} in, "
            f"{fmt_tokens(grand_total.output_tokens)} out"
        )

        return "\n".join(lines)


def get_usage_storage(storage: BaseStorage | None = None) -> UsageStorage:
    """Create a UsageStorage instance.

    Args:
        storage: Optional BaseStorage instance. Falls back to global get_storage().

    Returns:
        New UsageStorage instance wrapping the storage.
    """
    if storage is None:
        storage = get_storage()
    return UsageStorage(storage)

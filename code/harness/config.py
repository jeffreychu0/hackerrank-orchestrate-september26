"""Run-level configuration for the Buy or Wait? harness."""

from dataclasses import dataclass, field
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CODE_ROOT.parent
DEFAULT_DATASET = REPO_ROOT / "dataset"
#: The submission asks for predictions at the repository root; the dataset copy
#: keeps the supplied template filled in as the problem statement describes.
DEFAULT_OUTPUT = REPO_ROOT / "output.csv"
DEFAULT_OUTPUT_MIRRORS = (DEFAULT_DATASET / "output.csv",)
REPORTS_DIR = CODE_ROOT / "evaluation" / "reports"
#: Pinned by the submission contract: code.zip must contain
#: evaluation/usage_report.md at exactly this path.
DEFAULT_USAGE_REPORT = CODE_ROOT / "evaluation" / "usage_report.md"
DEFAULT_AUDIT_LOG = REPORTS_DIR / "evidence_audit.jsonl"

FORECAST_DAYS = 90

#: Which window a payment must keep safe. "completion" runs from the request date
#: through the later of desired_completion_date and the final payment - the window
#: in which the request is actually live, and the reading the supplied samples
#: follow for request_08, request_12 and request_13. "horizon" uses the full 90
#: days for plans too. amount_safe_to_pay is a 90-day measure either way.
SAFETY_WINDOW = "completion"
MAX_SPENDING_CHANGES = 3

DEFAULT_PROVIDER = "openai"

#: Per-provider list prices live in harness/providers.py; these remain as the
#: fallback when a run supplies neither a provider default nor a CLI override.
DEFAULT_INPUT_COST_PER_MTOK = 1.25
DEFAULT_OUTPUT_COST_PER_MTOK = 10.0


@dataclass(frozen=True)
class RecurrencePolicy:
    """Knobs the sample-calibration suite exercises; defaults are the tuned values."""

    min_occurrences: int = 2
    max_period_days: int = 40
    monthly_period_range: tuple[int, int] = (26, 33)
    amount_estimator: str = "mean"
    credit_estimator: str = ""
    #: "Forecast essential variable spending conservatively" - so the categories
    #: that move week to week may use a higher estimate than their plain mean.
    variable_estimator: str = ""
    #: A pattern whose last occurrence is this many periods stale has lapsed.
    stale_periods: float = 1.5
    #: How a credit pattern must look before it counts as confirmed future income:
    #: "off", "repeat" (a repeated exact amount) or "spread" (low relative range).
    income_stability: str = "off"
    income_spread_limit: float = 0.10
    income_window: int = 4
    #: How a confirmed future row in a category relates to that category's
    #: projected occurrences: "window" suppresses projections within
    #: explicit_match_window_days, "substitute" suppresses the single
    #: nearest projection within one period, "add" suppresses nothing.
    explicit_row_handling: str = "window"
    explicit_match_window_days: int = 3
    terminal_income_markers: tuple[str, ...] = ("final ", "last ", "terminated", "severance")


@dataclass(frozen=True)
class HarnessConfig:
    dataset: Path = DEFAULT_DATASET
    output: Path = DEFAULT_OUTPUT
    output_mirrors: tuple = DEFAULT_OUTPUT_MIRRORS
    usage_report: Path = DEFAULT_USAGE_REPORT
    audit_log: Path | None = DEFAULT_AUDIT_LOG
    forecast_days: int = FORECAST_DAYS
    safety_window: str = SAFETY_WINDOW
    provider: str = DEFAULT_PROVIDER
    use_model: bool = True
    explain_with_model: bool = True
    max_tool_calls: int = 12
    max_model_calls: int = 6
    workers: int = 4
    request_ids: tuple[str, ...] = ()
    include_samples: bool = False
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    recurrence: RecurrencePolicy = field(default_factory=RecurrencePolicy)

"""Cross-model evaluation: each provider adjudicates the other's evidence reading.

The supplied sample answers cover 25 requests. This eval works on any request
by replacing ground truth with cross-examination: two providers read the same
evidence independently, then each grades both readings blind. It measures its
own trustworthiness as it goes - self-preference bias is estimated from the two
judging directions, and judge calibration is checked against the sample answers.
"""

from . import dataset, judge, score

__all__ = ["dataset", "judge", "score"]

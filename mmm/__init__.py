"""mmm — shared methodology engine for the IHSG Macro Monitoring System.

This package holds the *common methodology* that every Macro Monitoring Module
(MMM) reuses: the observation data model, the HTTP/source helpers with the
anti-hallucination contract (failed fetch -> STALE, never a guessed value), the
verification helpers, the time-series store, the registry handling and the
static HTML renderer.

Individual domains live under ``modules/<id>/`` and only describe *what* to
fetch and *how to interpret it*. They lean on this package for the plumbing so
that consistency across modules is guaranteed by construction.
"""

__version__ = "0.1.0"

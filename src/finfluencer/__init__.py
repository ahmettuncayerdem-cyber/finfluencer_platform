"""
finfluencer — A reusable computational research platform for empirical studies
of financial YouTube communities, retail investor behaviour, and finfluencer
discourse.

See docs/product/PRODUCT_ARCHITECTURE.md for the module inventory and dependency graph.

The `__version__` attribute is the ONLY value below that end users should
depend on before the public API stabilises. Additional public exports will
be declared here as subpackages reach stability.

``__version__`` always mirrors this package's SemVer software version in
``pyproject.toml``'s ``[tool.poetry].version`` -- it is a distinct axis
from the research/citation version in ``CITATION.cff``. See
docs/VERSIONING.md for the full policy and rationale.
"""

__version__ = "0.1.0"

__all__: list[str] = []  # populated as public API stabilises across phases

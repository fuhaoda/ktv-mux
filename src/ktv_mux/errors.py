class KtvError(RuntimeError):
    """Base exception for user-facing pipeline errors."""


class MissingDependencyError(KtvError):
    """Raised when an optional external command or Python package is missing."""


class PipelineStateError(KtvError):
    """Raised when a requested stage is missing required inputs."""


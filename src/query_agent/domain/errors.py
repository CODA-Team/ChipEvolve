"""Named boundary errors."""


class QueryAgentError(Exception):
    """Base class for errors that should be reported at a boundary."""


class ArtifactProviderError(QueryAgentError):
    """The local artifact boundary rejected an operation."""


class ArtifactNotFoundError(ArtifactProviderError):
    """A requested artifact path does not exist."""


class ArtifactPathError(ArtifactProviderError):
    """A path is invalid or escapes the workspace sandbox."""


class BinaryArtifactError(ArtifactProviderError):
    """Text access was attempted on a binary artifact."""


class ArtifactLimitError(ArtifactProviderError):
    """A configured bounded-read limit was invalid."""


class RunEvidenceError(QueryAgentError):
    """The managed-run evidence boundary rejected an operation."""


class LLMContractError(QueryAgentError):
    """A LanguageModel adapter returned output outside its typed contract."""

"""Weekly editorial research for the Ironbound family of leagues."""

__version__ = "0.1.0"

# Install the completed-week Sleeper projection adapter before downstream
# modules import honors by name.  This keeps the public honors contract stable
# while allowing the deterministic registry to use Sleeper's retained week
# projections and expose a permanent audit trail.
from .historical_awards import install as _install_historical_awards

_install_historical_awards()
del _install_historical_awards

"""Robot Framework library for VMware NSX-T 4.x.

Import as ``Library  NSXLibrary`` (PyPI package ``nsx-robotframework``).
"""

from ._client import NSXClient, NSXError
from .NSXLibrary import NSXLibrary

__all__ = ["NSXClient", "NSXError", "NSXLibrary"]
__version__ = "0.1.0"

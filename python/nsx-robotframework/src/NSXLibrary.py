"""Top-level Robot Framework library shim.

Lets users write ``Library  NSXLibrary`` while the implementation lives in
the ``nsx_robotframework`` package (import name ``nsx_robotframework``).
"""

from nsx_robotframework.NSXLibrary import NSXLibrary

__all__ = ["NSXLibrary"]

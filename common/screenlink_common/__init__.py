"""ScreenLink common library — shared protocol definitions for server and client.

This package exists so both sides import the **same** message schemas, preventing
silent drift between the JSON formats the server expects and the client sends.
See ARCHITECTURE.md §6 for the canonical message specification.
"""

__version__ = "0.1.0"

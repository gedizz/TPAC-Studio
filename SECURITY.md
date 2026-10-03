# Security

TPAC Studio processes local asset files. It bounds container reads and explicit decodes, rejects unsupported variants, protects original inputs and verifies newly written records. Image libraries, OpenGL drivers, Blender importers and Python extensions are additional trust boundaries.

Run with ordinary user privileges and use a dedicated asset folder. The MCP server uses stdio; `--root` confines normal service path resolution but is not an operating-system sandbox. Do not expose it through an unauthenticated network wrapper.

Extensions are executable Python and must be trusted. Listing installed extensions does not execute them. Blender imports disable automatic Python execution, but still invoke a native application on the supplied input. Asset strings are never shell commands.

Saved workspaces embed assets and origin paths. Review their contents before sharing them, and remove confidential paths from diagnostic reports.

For sensitive vulnerabilities, use GitHub private vulnerability reporting when available. Otherwise, open an issue requesting a secure reporting channel without including exploit details or confidential samples. For ordinary parser failures, include the tool version, operation, error code and a minimal synthetic reproducer.

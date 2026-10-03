# Security and trust boundaries

TPAC Studio is a local asset tool. It bounds container reads and explicit decodes, rejects unsupported variants, protects source files and verifies newly written records. Those checks do not make untrusted binary parsers, image libraries, OpenGL drivers, Blender importers or Python plugins a complete security sandbox.

The MCP server is stdio-only. `--root` confines normal service path resolution; a privileged local process, symlink race or trusted extension can bypass that application-level boundary. Run with ordinary user privileges and a dedicated asset folder. Do not expose the stdio server through an unauthenticated network wrapper.

Installed extensions are executable Python and must be trusted. Merely listing extensions does not execute them. Blender auto-execution is disabled, but model import still invokes a separate native application on the chosen input. Asset strings are never shell commands.

Projects contain asset bytes and origin paths. Do not publish real workspaces or logs without review. Dependency limitations and malformed inputs are tracked as correctness concerns as well as potential security concerns.

No public vulnerability-reporting address has been configured yet. Before public release, the repository owner should enable GitHub private vulnerability reporting or publish a contact. Until then, contact the repository owner through the private repository rather than posting exploitable files publicly. Do not upload proprietary samples without permission.

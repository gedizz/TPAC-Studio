# Extensions

Extension API version **1** provides optional asset inspectors/editors. It does not provide a native game renderer or automatically make unsupported animation formats safe to distribute.

An extension implements the `AssetExtension` protocol in `tpac_studio.extensions`:

```python
name: str
api_version: int  # 1
license: str
supports(asset: Asset) -> bool
inspect(asset: Asset) -> dict
settings_schema() -> dict
edit(asset: Asset, values: dict) -> Asset
```

Results must be JSON-serializable with finite numbers. An edit returns an immutable replacement preserving the original GUID, name and type, unrelated bytes, and source provenance. Validate supported layout versions explicitly. Never import/load a provider based on text inside a package.

## Install the example

[examples/extension](../examples/extension/) contains an MIT example provider that wraps existing supported particle opacity editing. It includes its own `pyproject.toml` and registers under the `tpac_studio.extensions` entry-point group.

```powershell
python -m pip install ./examples/extension
tpac-studio extensions_list
tpac-studio extension_schema --extension example-opacity --args '{"provider":"example-opacity"}'
```

Depending on shell quoting, pass the arguments in a `--request` file instead. For MCP, add `--extension example-opacity` to the **host's** server startup arguments. Listing installed extensions reads entry-point metadata without executing them. Loading one executes installed Python code. There is intentionally no tool allowing an untrusted asset or remote request to enable a new provider.

In Python:

```python
from tpac_studio.service import Studio
from example_opacity import ExampleOpacity

studio = Studio()
try:
    studio.registry.register(ExampleOpacity())
    studio.examples_load()
    response = studio.execute("extension_edit", {
        "provider": "example-opacity", "asset": "demo_smoke",
        "values": {"opacity": 0.75}, "expected_revision": 1
    })
    print(response)
finally:
    studio.close()
```

The service validates the provider schema before editing and applies the normal revision/identity checks. `extension_inspect` and `extension_schema` discover enabled capabilities. The generic desktop does not automatically create extension panels; use Python, CLI or MCP until such a frontend is implemented.

Providers can perform arbitrary I/O in Python. The service root is not an extension sandbox. Review provider code, dependencies and licenses before installation.

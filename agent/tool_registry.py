import asyncio
import json
from typing import Any, Callable, Dict, List, Optional


class ToolRegistry:
    """
    Simple registry to expose tools (name, description, json-schema params)
    and dispatch calls from an LLM-driven function-calling flow.
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, description: str, parameters: Optional[Dict] = None):
        """Decorator to register a function as a tool."""

        def _decorator(fn: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters or {},
                "fn": fn,
            }
            return fn

        return _decorator

    def register_fn(self, name: str, fn: Callable, description: str, parameters: Optional[Dict] = None):
        """Register a callable directly."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
            "fn": fn,
        }

    def get_tools_for_model(self) -> List[Dict[str, Any]]:
        """Return a list of tool metadata suitable to pass to model APIs."""
        tools = []
        for t in self._tools.values():
            tools.append({
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            })
        return tools

    async def execute(self, name: str, arguments: Any) -> Any:
        """Execute a registered tool. `arguments` can be dict or JSON string."""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")

        entry = self._tools[name]
        fn = entry["fn"]

        # normalize arguments
        args = {}
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except Exception:
                # try very small parsing like 'url=https://...'
                parts = [p.strip() for p in arguments.split("&") if p.strip()]
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        args[k] = v
        elif isinstance(arguments, dict):
            args = arguments

        # call fn (support coroutine functions)
        if asyncio.iscoroutinefunction(fn):
            return await fn(**args)
        else:
            return fn(**args)


# module-level singleton registry
registry = ToolRegistry()

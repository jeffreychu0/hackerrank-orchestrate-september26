"""Provider-neutral tool contracts and validated dispatch."""

from dataclasses import dataclass, field
import json
from typing import Any, Callable


class ToolError(ValueError):
    """Expected, safe-to-display tool input or data error."""


@dataclass(frozen=True)
class ImageAttachment:
    image_id: str
    data: bytes = field(repr=False)
    mime_type: str = "image/png"


@dataclass
class ToolResult:
    data: dict[str, Any]
    images: list[ImageAttachment] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


def object_schema(**properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def validate(value, schema):
    """Validate the deliberately small schema subset used by this registry.

    Provider strict mode is not a substitute for validation at dispatch.
    """
    kind = schema["type"]
    kinds = kind if isinstance(kind, list) else [kind]
    matches = {"null": value is None, "string": isinstance(value, str),
               "integer": type(value) is int, "object": isinstance(value, dict)}
    if not any(matches.get(k, False) for k in kinds):
        raise ToolError("Tool argument has an invalid type.")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolError("Tool argument is outside its allowed values.")
    if value is None:
        return
    if kind == "object":
        props = schema["properties"]
        if set(value) != set(props):
            raise ToolError("Supply exactly the declared tool arguments; use null for unused filters.")
        for name in props:
            validate(value[name], props[name])
    if type(value) is int:
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            raise ToolError("Tool argument is outside its allowed range.")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., ToolResult]]] = {}

    @property
    def definitions(self):
        return [item[0] for item in self._tools.values()]

    def register(self, definition: ToolDefinition, handler: Callable[..., ToolResult]):
        if definition.name in self._tools:
            raise ValueError("Duplicate tool name.")
        self._tools[definition.name] = (definition, handler)

    def execute(self, name: str, arguments: dict | str) -> ToolResult:
        try:
            if name not in self._tools:
                raise ToolError("Unknown tool.")
            if isinstance(arguments, str):
                if len(arguments) > 16000:
                    raise ToolError("Tool arguments are too large.")
                try:
                    arguments = json.loads(arguments)
                except (ValueError, RecursionError):
                    raise ToolError("Tool arguments must be valid JSON.") from None
            definition, handler = self._tools[name]
            validate(arguments, definition.parameters)
            return handler(**arguments)
        except ToolError as exc:
            return ToolResult({"ok": False, "error": str(exc)})


def success(**data):
    return ToolResult({"ok": True, **data})

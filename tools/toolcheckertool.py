from tools.base import BaseTool
import re
import json
from typing import Dict
import os
from pathlib import Path

class ToolCheckerTool(BaseTool):
    name = "toolcheckertool"
    description = '''
    Validates if a tool implementation follows the required BaseTool interface:
    - Has required properties (name, description, input_schema)
    - Name follows the regex pattern ^[a-zA-Z0-9_-]{1,64}$
    - Input schema is valid JSON schema
    - Has execute method with correct signature
    - Validates file paths and directory structures
    - Performs path validation checks for path-related properties
    - Ensures proper directory permissions and creation capabilities
    '''
    input_schema = {
        "type": "object",
        "properties": {
            "tool_code": {
                "type": "string",
                "description": "Python code of the tool implementation to check"
            }
        },
        "required": ["tool_code"]
    }

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate if a path is properly formatted and accessible."""
        try:
            path_obj = Path(path)

            # Check if path is absolute
            if not path_obj.is_absolute():
                return False, "Path must be absolute"

            # Check if parent directory exists or is creatable
            parent = path_obj.parent
            if not parent.exists():
                try:
                    # Test if we can create the directory
                    os.makedirs(parent, exist_ok=True)
                    os.rmdir(parent)  # Clean up test directory
                except (OSError, PermissionError) as e:
                    return False, f"Cannot create parent directory: {str(e)}"

            # Check if we have write permission in the parent directory
            if parent.exists() and not os.access(parent, os.W_OK):
                return False, "No write permission in parent directory"

            return True, "Path is valid"

        except Exception as e:
            return False, f"Invalid path: {str(e)}"

    def execute(self, **kwargs) -> str:
        tool_code = kwargs["tool_code"]

        # Check if code is valid Python
        try:
            exec(tool_code)
        except Exception as e:
            return f"Invalid Python code: {str(e)}"

        # Find tool class definition
        class_match = re.search(r'class\s+(\w+)\s*\(\s*BaseTool\s*\)', tool_code)
        if not class_match:
            return "No tool class found that inherits from BaseTool"

        class_name = class_match.group(1)

        # Extract properties
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', tool_code)
        if not name_match:
            return "Missing name property"

        name = name_match.group(1)
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', name):
            return f"Invalid name '{name}' - must match pattern ^[a-zA-Z0-9_-]{{1,64}}$"

        if not re.search(r'description\s*=', tool_code):
            return "Missing description property"

        schema_match = re.search(r'input_schema\s*=\s*({[^}]+})', tool_code)
        if not schema_match:
            return "Missing input_schema property"

        # Validate input schema
        try:
            schema = eval(schema_match.group(1))
            if not isinstance(schema, dict):
                return "input_schema must be a dictionary"

            if schema.get("type") != "object":
                return "input_schema must have type: 'object'"

            if "properties" not in schema:
                return "input_schema must have 'properties' field"

            # Check for path-related properties
            for prop_name, prop_schema in schema.get("properties", {}).items():
                if any(path_term in prop_name.lower() for path_term in ["path", "directory", "file"]):
                    # Test a sample path
                    test_path = "/test/path/example"
                    is_valid, error = self.validate_path(test_path)
                    if not is_valid:
                        return f"Path validation failed for property '{prop_name}': {error}"

        except Exception as e:
            return f"Invalid input_schema: {str(e)}"

        # Check execute method
        if not re.search(r'def\s+execute\s*\(\s*self\s*,\s*\*\*\s*kwargs\s*\)\s*->\s*str\s*:', tool_code):
            return "Missing execute method with signature: def execute(self, **kwargs) -> str"

        return f"Tool implementation is valid!\nClass: {class_name}\nName: {name}"

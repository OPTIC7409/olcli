"""
OLCLI Scaffolding Tools
Tools for generating boilerplate code and project templates.
"""

from pathlib import Path
from typing import Dict, List, Optional
from .builtins import ToolResult


# Template definitions
TEMPLATES = {
    "python-class": """class {class_name}:
    \"\"\"
    {description}
    \"\"\"
    
    def __init__(self{init_params}):
        {init_body}
    
    def __repr__(self):
        return f"{class_name}({repr_body})"
""",
    
    "python-function": """def {function_name}({params}){return_annotation}:
    \"\"\"
    {description}
    {args_doc}
    {returns_doc}
    \"\"\"
    {body}
""",
    
    "python-test": """import unittest
from {module} import {class_name}


class Test{class_name}(unittest.TestCase):
    \"\"\"Tests for {class_name}.\"\"\"
    
    def setUp(self):
        \"\"\"Set up test fixtures.\"\"\"
        self.instance = {class_name}()
    
    def test_{test_name}(self):
        \"\"\"Test {test_description}.\"\"\"
        # Arrange
        
        # Act
        result = self.instance.{method}()
        
        # Assert
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
""",
    
    "python-cli": """#!/usr/bin/env python3
\"\"\"
{description}
\"\"\"

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("input", help="Input file or directory")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Main logic here
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
""",
    
    "python-api": """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="{api_title}", version="{version}")


class {model_name}(BaseModel):
    {fields}


@app.get("/")
async def root():
    return {{"message": "Welcome to {api_title}"}}


@app.get("/items/{{item_id}}")
async def get_item(item_id: int):
    return {{"item_id": item_id}}


@app.post("/items/")
async def create_item(item: {model_name}):
    return item
""",
    
    "markdown-doc": """# {title}

## Overview

{description}

## Installation

```bash
pip install {package_name}
```

## Usage

```python
import {package_name}

# Example usage here
```

## API Reference

### {main_class}

{api_description}

## License

{license}
""",
    
    "dockerfile": """FROM {base_image}

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run
CMD ["python", "{entry_point}"]
""",
    
    "github-action": """name: {workflow_name}

on:
  push:
    branches: [{branches}]
  pull_request:
    branches: [{branches}]

jobs:
  {job_name}:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '{python_version}'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest
""",
}


def generate_from_template(template_name: str, variables: Dict[str, str]) -> ToolResult:
    """Generate code from a template."""
    if template_name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        return ToolResult(
            success=False,
            output="",
            error=f"Unknown template: {template_name}. Available: {available}"
        )
    
    template = TEMPLATES[template_name]
    try:
        content = template.format(**variables)
        return ToolResult(
            success=True,
            output=content,
            metadata={"template": template_name, "variables": list(variables.keys())}
        )
    except KeyError as e:
        return ToolResult(
            success=False,
            output="",
            error=f"Missing variable: {e}. Required variables depend on template."
        )


def scaffold_project(
    name: str,
    project_type: str = "python",
    path: str = ".",
    include_tests: bool = True,
    include_docs: bool = True,
    include_ci: bool = False
) -> ToolResult:
    """Scaffold a new project with standard structure."""
    base_path = Path(path).expanduser() / name
    
    if base_path.exists():
        return ToolResult(success=False, output="", error=f"Directory already exists: {base_path}")
    
    try:
        # Create directory structure
        dirs = [base_path, base_path / name]
        if include_tests:
            dirs.append(base_path / "tests")
        if include_docs:
            dirs.append(base_path / "docs")
        
        for d in dirs:
            d.mkdir(parents=True)
        
        files_created = []
        
        # __init__.py
        init_file = base_path / name / "__init__.py"
        init_file.write_text(f'"""{name} package."""\n\n__version__ = "0.1.0"\n')
        files_created.append(str(init_file))
        
        # Main module
        main_file = base_path / name / "main.py"
        main_content = generate_from_template("python-cli", {
            "description": f"CLI for {name}",
        }).output
        main_file.write_text(main_content)
        files_created.append(str(main_file))
        
        # README.md
        readme = base_path / "README.md"
        readme_content = generate_from_template("markdown-doc", {
            "title": name,
            "description": f"A Python package for {name}",
            "package_name": name,
            "main_class": "MainClass",
            "api_description": "Main API documentation",
            "license": "MIT",
        }).output
        readme.write_text(readme_content)
        files_created.append(str(readme))
        
        # requirements.txt
        req_file = base_path / "requirements.txt"
        req_file.write_text("# Add your dependencies here\n")
        files_created.append(str(req_file))
        
        # .gitignore
        gitignore = base_path / ".gitignore"
        gitignore.write_text("""__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
.env
.venv
venv/
""")
        files_created.append(str(gitignore))
        
        if include_tests:
            test_file = base_path / "tests" / "test_main.py"
            test_content = generate_from_template("python-test", {
                "module": name,
                "class_name": "MainClass",
                "test_name": "example",
                "test_description": "basic functionality",
                "method": "method_name",
            }).output
            test_file.write_text(test_content)
            files_created.append(str(test_file))
        
        if include_ci:
            github_dir = base_path / ".github" / "workflows"
            github_dir.mkdir(parents=True)
            ci_file = github_dir / "ci.yml"
            ci_content = generate_from_template("github-action", {
                "workflow_name": "CI",
                "branches": "main",
                "job_name": "test",
                "python_version": "3.11",
            }).output
            ci_file.write_text(ci_content)
            files_created.append(str(ci_file))
        
        output = f"# Scaffolding Complete\n\n"
        output += f"Created project: {name}\n"
        output += f"Location: {base_path}\n\n"
        output += "## Files Created:\n"
        for f in files_created:
            output += f"- {f}\n"
        
        return ToolResult(
            success=True,
            output=output,
            metadata={"project_path": str(base_path), "files": files_created}
        )
        
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def list_templates() -> ToolResult:
    """List available templates."""
    descriptions = {
        "python-class": "Python class with __init__ and __repr__",
        "python-function": "Python function with docstring",
        "python-test": "Unit test class",
        "python-cli": "Command-line interface script",
        "python-api": "FastAPI application",
        "markdown-doc": "Documentation in Markdown",
        "dockerfile": "Docker container definition",
        "github-action": "GitHub Actions workflow",
    }
    
    lines = ["# Available Templates", ""]
    for name, desc in descriptions.items():
        lines.append(f"- **{name}**: {desc}")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"templates": list(TEMPLATES.keys())}
    )

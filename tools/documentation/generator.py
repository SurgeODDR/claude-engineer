from typing import Dict, List, Optional
import os
import ast
from pathlib import Path

class DocumentationGenerator:
    def __init__(self):
        self.exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv'}
        self.exclude_files = {'.pyc', '.pyo', '.pyd', '.so', '.dll'}

    def generate_tree_structure(self, path: str) -> str:
        """Generate tree-like structure using unicode chars"""
        tree = []
        root = Path(path)

        def add_to_tree(directory: Path, prefix: str = ''):
            entries = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))

            for i, entry in enumerate(entries):
                if entry.name in self.exclude_dirs or any(entry.name.endswith(ext) for ext in self.exclude_files):
                    continue

                is_last = i == len(entries) - 1
                connector = '└── ' if is_last else '├── '
                tree.append(f'{prefix}{connector}{entry.name}')

                if entry.is_dir():
                    new_prefix = prefix + ('    ' if is_last else '│   ')
                    add_to_tree(entry, new_prefix)

        add_to_tree(root)
        return '\n'.join(tree)

    def extract_file_contents(self, path: str) -> str:
        """Extract and format file contents with separators"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            separator = '=' * 48
            return f"File: {path}\n{separator}\n{content}\n{separator}\n"
        except Exception as e:
            return f"Error reading {path}: {str(e)}"

    def analyze_code_relationships(self, path: str) -> Dict:
        """Analyze imports, function calls, and dependencies"""
        relationships = {
            'imports': [],
            'functions': {},
            'variables': set(),
            'dependencies': set()
        }

        class CodeAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None

            def visit_Import(self, node):
                for name in node.names:
                    relationships['imports'].append(name.name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                module = node.module or ''
                for name in node.names:
                    full_import = f"{module}.{name.name}" if module else name.name
                    relationships['imports'].append(full_import)
                self.generic_visit(node)

            def visit_FunctionDef(self, node):
                prev_function = self.current_function
                self.current_function = node.name
                relationships['functions'][node.name] = {
                    'calls': set(),
                    'variables': set(),
                    'line_number': node.lineno
                }
                self.generic_visit(node)
                self.current_function = prev_function

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and self.current_function:
                    relationships['functions'][self.current_function]['calls'].add(node.func.id)
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    relationships['variables'].add(node.id)
                    if self.current_function:
                        relationships['functions'][self.current_function]['variables'].add(node.id)
                self.generic_visit(node)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=path)
                analyzer = CodeAnalyzer()
                analyzer.visit(tree)

                # Convert sets to lists for JSON serialization
                relationships['variables'] = list(relationships['variables'])
                for func_name in relationships['functions']:
                    relationships['functions'][func_name]['calls'] = list(
                        relationships['functions'][func_name]['calls']
                    )
                    relationships['functions'][func_name]['variables'] = list(
                        relationships['functions'][func_name]['variables']
                    )

                return relationships
        except Exception as e:
            return {
                'error': f"Error analyzing {path}: {str(e)}",
                'imports': [],
                'functions': {},
                'variables': [],
                'dependencies': []
            }

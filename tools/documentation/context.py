from typing import Dict, List, Optional, Set
import ast
import os
from pathlib import Path
from .generator import DocumentationGenerator
from .cache import DocumentationCache

class ContextProvider:
    def __init__(self):
        self.generator = DocumentationGenerator()
        self.cache = DocumentationCache()
        self.relationship_cache: Dict[str, Dict] = {}

    def get_context_for_file(self, file_path: str) -> Dict[str, any]:
        """Get relevant documentation context for file"""
        repo_path = self._get_repo_path(file_path)
        if not repo_path:
            return {'error': 'File not in a git repository'}

        # Get or analyze relationships
        relationships = self._get_relationships(repo_path)
        if not relationships:
            return {'error': 'Failed to analyze code relationships'}

        file_rel_path = os.path.relpath(file_path, repo_path)

        # Get direct relationships for this file
        direct_relations = self._get_direct_relationships(file_rel_path, relationships)

        # Get cached documentation
        cached_doc = self.cache.get_cached_doc(repo_path)
        if not cached_doc:
            return {
                'relationships': direct_relations,
                'documentation': None,
                'warning': 'Documentation cache not available'
            }

        # Extract relevant documentation sections
        relevant_docs = self._extract_relevant_sections(
            cached_doc['documentation'],
            direct_relations['related_files']
        )

        return {
            'relationships': direct_relations,
            'documentation': relevant_docs,
            'metadata': cached_doc.get('metadata', {})
        }

    def analyze_edit_impact(self, file_path: str, edit: str) -> Dict[str, any]:
        """Analyze potential impact of file edit"""
        repo_path = self._get_repo_path(file_path)
        if not repo_path:
            return {'error': 'File not in a git repository'}

        # Parse the edit to understand changes
        try:
            edit_tree = ast.parse(edit)
        except Exception:
            return {'error': 'Invalid Python syntax in edit'}

        # Analyze what's being modified
        edit_analyzer = self._EditAnalyzer()
        edit_analyzer.visit(edit_tree)

        # Get existing relationships
        relationships = self._get_relationships(repo_path)
        if not relationships:
            return {'error': 'Failed to analyze code relationships'}

        file_rel_path = os.path.relpath(file_path, repo_path)

        # Analyze impact
        impact = self._analyze_impact(
            file_rel_path,
            relationships,
            edit_analyzer.modified_elements
        )

        return {
            'impact': impact,
            'modified_elements': edit_analyzer.modified_elements,
            'affected_files': list(impact['affected_files']),
            'risk_level': impact['risk_level'],
            'warnings': impact['warnings']
        }

    def _get_repo_path(self, file_path: str) -> Optional[str]:
        """Get the root path of the git repository containing the file"""
        current = Path(file_path).resolve().parent
        while current != current.parent:
            if (current / '.git').is_dir():
                return str(current)
            current = current.parent
        return None

    def _get_relationships(self, repo_path: str) -> Optional[Dict]:
        """Get or generate code relationships for the repository"""
        if repo_path in self.relationship_cache:
            return self.relationship_cache[repo_path]

        relationships = {}
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    try:
                        relationships[rel_path] = self.generator.analyze_code_relationships(file_path)
                    except Exception:
                        continue

        if relationships:
            self.relationship_cache[repo_path] = relationships
            return relationships
        return None

    def _get_direct_relationships(self, file_path: str, relationships: Dict) -> Dict:
        """Get direct relationships for a specific file"""
        if file_path not in relationships:
            return {'error': f'No relationships found for {file_path}'}

        file_rels = relationships[file_path]
        related_files = set()

        # Files that import this file
        for other_file, other_rels in relationships.items():
            if other_file == file_path:
                continue

            # Check imports
            for imp in other_rels.get('imports', []):
                if file_path.replace('/', '.').replace('.py', '') in imp:
                    related_files.add(other_file)

            # Check function calls
            for func_data in other_rels.get('functions', {}).values():
                if any(call in file_rels.get('functions', {}) for call in func_data.get('calls', [])):
                    related_files.add(other_file)

        return {
            'imports': file_rels.get('imports', []),
            'functions': file_rels.get('functions', {}),
            'variables': file_rels.get('variables', []),
            'related_files': list(related_files)
        }

    def _extract_relevant_sections(self, documentation: str, related_files: List[str]) -> Dict[str, str]:
        """Extract documentation sections relevant to the related files"""
        sections = {}
        current_file = None
        current_content = []

        for line in documentation.split('\n'):
            if line.startswith('File: '):
                if current_file and current_content:
                    sections[current_file] = '\n'.join(current_content)
                current_file = line[6:].strip()
                current_content = [line]
            elif any(rel_file in line for rel_file in related_files):
                current_content.append(line)
            elif current_file and current_content:
                current_content.append(line)

        if current_file and current_content:
            sections[current_file] = '\n'.join(current_content)

        return sections

    class _EditAnalyzer(ast.NodeVisitor):
        """Analyze what elements are being modified in an edit"""
        def __init__(self):
            self.modified_elements = {
                'functions': set(),
                'variables': set(),
                'imports': set(),
                'classes': set()
            }

        def visit_FunctionDef(self, node):
            self.modified_elements['functions'].add(node.name)
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            self.modified_elements['classes'].add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node):
            for name in node.names:
                self.modified_elements['imports'].add(name.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            module = node.module or ''
            for name in node.names:
                full_import = f"{module}.{name.name}" if module else name.name
                self.modified_elements['imports'].add(full_import)
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.modified_elements['variables'].add(target.id)
            self.generic_visit(node)

    def _analyze_impact(self, file_path: str, relationships: Dict, modified_elements: Dict) -> Dict:
        """Analyze the impact of modifications on related files"""
        affected_files = set()
        warnings = []
        risk_level = 'low'

        # Check each file's relationships
        for other_file, other_rels in relationships.items():
            if other_file == file_path:
                continue

            # Check if modified functions are called
            for func_name in modified_elements['functions']:
                for other_func, func_data in other_rels.get('functions', {}).items():
                    if func_name in func_data.get('calls', []):
                        affected_files.add(other_file)
                        warnings.append(f"Function '{func_name}' is called in {other_file}")
                        risk_level = 'medium'

            # Check if modified variables are used
            for var_name in modified_elements['variables']:
                if var_name in other_rels.get('variables', []):
                    affected_files.add(other_file)
                    warnings.append(f"Variable '{var_name}' is used in {other_file}")
                    risk_level = 'medium'

            # Check import dependencies
            file_module = file_path.replace('/', '.').replace('.py', '')
            for imp in other_rels.get('imports', []):
                if file_module in imp:
                    affected_files.add(other_file)
                    warnings.append(f"Module is imported in {other_file}")
                    risk_level = 'high'

        return {
            'affected_files': affected_files,
            'warnings': warnings,
            'risk_level': risk_level
        }

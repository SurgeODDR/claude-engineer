from typing import Dict, List, Optional
import os
from pathlib import Path
from .generator import DocumentationGenerator
from .cache import DocumentationCache
from .context import ContextProvider

class DocumentationHandler:
    def __init__(self):
        self.generator = DocumentationGenerator()
        self.cache = DocumentationCache()
        self.context = ContextProvider()
        self.current_repo: Optional[str] = None
        self.loaded_chunks: Dict[str, List[str]] = {}

    def handle_file_edit(self, file_path: str, edit: Optional[str] = None) -> Dict:
        """Handle file edit request with documentation context"""
        try:
            # Get repository path
            repo_path = self._get_repo_path(file_path)
            if not repo_path:
                return {'error': 'File not in a git repository'}

            # Update current repository context
            if self.current_repo != repo_path:
                self.current_repo = repo_path
                self.loaded_chunks = {}

            # Get or generate documentation
            documentation = self._get_or_generate_doc(repo_path)
            if not documentation:
                return {'error': 'Failed to generate documentation'}

            # Get file context
            context = self.context.get_context_for_file(file_path)
            if 'error' in context:
                return context

            # If edit provided, analyze impact
            impact = None
            if edit:
                impact = self.context.analyze_edit_impact(file_path, edit)

            return {
                'documentation': documentation,
                'context': context,
                'impact': impact,
                'metadata': {
                    'repo_path': repo_path,
                    'file_path': file_path,
                    'has_cached_doc': bool(self.cache.get_cached_doc(repo_path))
                }
            }
        except Exception as e:
            return {'error': f'Handler error: {str(e)}'}

    def get_documentation_chunk(self, repo_path: str, chunk_index: int) -> Optional[str]:
        """Get a specific chunk of documentation (lazy loading)"""
        if not self._get_repo_path(repo_path):
            return None

        # Try to get from loaded chunks
        if repo_path in self.loaded_chunks and 0 <= chunk_index < len(self.loaded_chunks[repo_path]):
            return self.loaded_chunks[repo_path][chunk_index]

        # Try to get from cache
        chunk = self.cache.get_cached_chunk(repo_path, chunk_index)
        if chunk:
            if repo_path not in self.loaded_chunks:
                self.loaded_chunks[repo_path] = []
            while len(self.loaded_chunks[repo_path]) <= chunk_index:
                self.loaded_chunks[repo_path].append('')
            self.loaded_chunks[repo_path][chunk_index] = chunk
            return chunk

        return None

    def refresh_documentation(self, repo_path: str) -> Dict:
        """Force refresh documentation for a repository"""
        try:
            if not self._get_repo_path(repo_path):
                return {'error': 'Invalid repository path'}

            # Clear cache and loaded chunks
            self.cache.invalidate_cache(repo_path)
            if repo_path in self.loaded_chunks:
                del self.loaded_chunks[repo_path]

            # Generate fresh documentation
            documentation = self._generate_documentation(repo_path)
            if not documentation:
                return {'error': 'Failed to generate documentation'}

            return {
                'documentation': documentation,
                'metadata': {
                    'repo_path': repo_path,
                    'cached': True,
                    'chunks': len(self.loaded_chunks.get(repo_path, []))
                }
            }
        except Exception as e:
            return {'error': f'Refresh error: {str(e)}'}

    def _get_repo_path(self, path: str) -> Optional[str]:
        """Get the root path of the git repository"""
        current = Path(path).resolve().parent
        while current != current.parent:
            if (current / '.git').is_dir():
                return str(current)
            current = current.parent
        return None

    def _get_or_generate_doc(self, repo_path: str) -> Optional[Dict]:
        """Get cached documentation or generate new one"""
        # Try to get from cache first
        cached_doc = self.cache.get_cached_doc(repo_path)
        if cached_doc:
            return cached_doc

        # Generate new documentation
        return self._generate_documentation(repo_path)

    def _generate_documentation(self, repo_path: str) -> Optional[Dict]:
        """Generate documentation for a repository"""
        try:
            # Generate tree structure
            tree = self.generator.generate_tree_structure(repo_path)

            # Generate file contents
            contents = []
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.md')):
                        file_path = os.path.join(root, file)
                        content = self.generator.extract_file_contents(file_path)
                        contents.append(content)

            # Analyze relationships
            relationships = {}
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_path)
                        relationships[rel_path] = self.generator.analyze_code_relationships(file_path)

            documentation = {
                'tree': tree,
                'contents': '\n'.join(contents),
                'relationships': relationships
            }

            # Cache the documentation
            self.cache.cache_doc(repo_path, documentation, {
                'files_analyzed': len(contents),
                'relationships_found': len(relationships)
            })

            return documentation
        except Exception:
            return None

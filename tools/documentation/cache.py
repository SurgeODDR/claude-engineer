from typing import Dict, List, Optional
import os
import json
import time
import hashlib
from pathlib import Path

class DocumentationCache:
    def __init__(self):
        self.cache_dir = os.path.expanduser("~/.cache/llm_docs")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_expiry = 24 * 60 * 60  # 24 hours in seconds
        self.chunk_size = 1000  # tokens per chunk (approximate)

    def _get_cache_path(self, repo_path: str) -> str:
        """Get cache file path for a repository"""
        repo_hash = hashlib.sha256(repo_path.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{repo_hash}.json")

    def _calculate_file_checksums(self, repo_path: str) -> Dict[str, str]:
        """Calculate checksums for all files in repository"""
        checksums = {}
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.md')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'rb') as f:
                            checksums[os.path.relpath(file_path, repo_path)] = \
                                hashlib.sha256(f.read()).hexdigest()
                    except Exception:
                        continue
        return checksums

    def get_cached_doc(self, repo_path: str) -> Optional[Dict]:
        """Get cached documentation if valid"""
        cache_path = self._get_cache_path(repo_path)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            # Check cache expiry
            if time.time() - cache_data['timestamp'] > self.cache_expiry:
                return None

            # Check file checksums
            current_checksums = self._calculate_file_checksums(repo_path)
            if current_checksums != cache_data['checksums']:
                return None

            return {
                'documentation': cache_data['documentation'],
                'chunks': cache_data['chunks'],
                'metadata': cache_data['metadata']
            }
        except Exception:
            return None

    def cache_doc(self, repo_path: str, documentation: str, metadata: Dict) -> None:
        """Cache documentation with metadata"""
        cache_path = self._get_cache_path(repo_path)

        # Calculate checksums for all files
        checksums = self._calculate_file_checksums(repo_path)

        # Split documentation into chunks for lazy loading
        chunks = []
        current_chunk = []
        current_size = 0

        for line in documentation.split('\n'):
            line_size = len(line.split())  # Approximate token count
            if current_size + line_size > self.chunk_size:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        cache_data = {
            'timestamp': time.time(),
            'checksums': checksums,
            'documentation': documentation,
            'chunks': chunks,
            'metadata': metadata
        }

        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except Exception:
            # If caching fails, we'll just regenerate next time
            pass

    def invalidate_cache(self, repo_path: str) -> None:
        """Invalidate cache for a repository"""
        cache_path = self._get_cache_path(repo_path)
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
        except Exception:
            pass

    def get_cached_chunk(self, repo_path: str, chunk_index: int) -> Optional[str]:
        """Get a specific chunk of documentation for lazy loading"""
        cache_data = self.get_cached_doc(repo_path)
        if not cache_data or 'chunks' not in cache_data:
            return None

        chunks = cache_data['chunks']
        if 0 <= chunk_index < len(chunks):
            return chunks[chunk_index]
        return None

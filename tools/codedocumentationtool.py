from tools.base import BaseTool
import json
from pathlib import Path
import os
from tokencost import count_string_tokens
import chardet

class CodeDocumentationTool(BaseTool):
    name = "codedocumentationtool"
    description = '''
    Generates and manages documentation for code files.
    - Creates summaries of code files
    - Stores documentation for future context
    - Optimizes token usage
    - Provides relevant context for code understanding
    - Supports multiple file types and nested directories
    '''

    input_schema = {
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of file paths to document"
            }
        },
        "required": ["file_paths"]
    }

    def __init__(self):
        self.docs_dir = Path(__file__).parent.parent / "docs"
        self.docs_dir.mkdir(exist_ok=True)
        self.max_file_size = 1000000  # 1MB
        self.ignore_patterns = [
            '*.pyc', '__pycache__', '.git', 'node_modules',
            '*.jpg', '*.png', '*.gif', '*.pdf', '*.zip'
        ]

    def _create_summary(self, content: str) -> str:
        lines = content.split('\n')
        summary_lines = []

        if len(lines) > 0 and lines[0].startswith('"""'):
            doc_end = next((i for i, line in enumerate(lines) if i > 0 and line.endswith('"""')), None)
            if doc_end:
                summary_lines = lines[1:doc_end]

        if not summary_lines:
            summary_lines = [line for line in lines[:10] if line.strip()][:5]

        return '\n'.join(summary_lines).strip()

    def _generate_doc(self, file_path: str) -> dict:
        with open(file_path, 'rb') as f:
            raw_content = f.read()
            encoding = chardet.detect(raw_content)['encoding'] or 'utf-8'

        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()

        doc = {
            'path': file_path,
            'content': content,
            'summary': self._create_summary(content),
            'token_count': count_string_tokens(content)
        }

        doc_path = self.docs_dir / f"{Path(file_path).stem}.json"
        with open(doc_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        return doc

    def _optimize_context(self, docs: list) -> str:
        MAX_TOKENS = 4000  # Reserve tokens for model response
        total_tokens = 0
        context = []

        for doc in sorted(docs, key=lambda x: x['token_count']):
            doc_context = f"File: {doc['path']}\n{doc['summary']}\n"
            doc_tokens = count_string_tokens(doc_context)

            if total_tokens + doc_tokens > MAX_TOKENS:
                break

            context.append(doc_context)
            total_tokens += doc_tokens

        return "\n".join(context)

    def execute(self, **kwargs) -> str:
        file_paths = kwargs.get('file_paths', [])
        docs = []

        for path in file_paths:
            if not os.path.exists(path):
                continue
            if any(p in path for p in self.ignore_patterns):
                continue

            try:
                if os.path.getsize(path) > self.max_file_size:
                    continue

                doc = self._generate_doc(path)
                docs.append(doc)
            except Exception as e:
                print(f"Error processing {path}: {str(e)}")

        context = self._optimize_context(docs)
        return context

import os
import tempfile
import shutil
import time
from pathlib import Path
from unittest import TestCase, mock
from tools.documentation.generator import DocumentationGenerator
from tools.documentation.cache import DocumentationCache
from tools.documentation.context import ContextProvider

class TestDocumentation(TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.test_dir))

        # Create test files
        self.create_test_files()

        # Initialize components
        self.generator = DocumentationGenerator()
        self.cache = DocumentationCache()
        self.context = ContextProvider()

    def create_test_files(self):
        """Create test file structure"""
        # Create main.py
        main_content = """
import utils
from models import User

def main():
    user = User()
    result = utils.process_data(user)
    return result
"""
        self.create_file("main.py", main_content)

        # Create utils.py
        utils_content = """
def process_data(user):
    return user.get_data()
"""
        self.create_file("utils.py", utils_content)

        # Create models.py
        models_content = """
class User:
    def get_data(self):
        return {'id': 1}
"""
        self.create_file("models.py", models_content)

        # Create some files to be excluded
        os.makedirs(os.path.join(self.test_dir, "__pycache__"))
        os.makedirs(os.path.join(self.test_dir, ".git"))

    def create_file(self, name: str, content: str):
        """Helper to create test files"""
        path = os.path.join(self.test_dir, name)
        with open(path, 'w') as f:
            f.write(content.strip())

    def test_tree_generation(self):
        """Test directory tree generation"""
        # Generate tree
        tree = self.generator.generate_tree_structure(self.test_dir)

        # Verify structure
        self.assertIn("├── main.py", tree)
        self.assertIn("├── models.py", tree)
        self.assertIn("└── utils.py", tree)

        # Verify exclusions
        self.assertNotIn("__pycache__", tree)
        self.assertNotIn(".git", tree)

    def test_caching(self):
        """Test documentation caching"""
        # Generate and cache documentation
        doc_content = "Test documentation content"
        metadata = {"test": True}
        self.cache.cache_doc(self.test_dir, doc_content, metadata)

        # Verify cache retrieval
        cached = self.cache.get_cached_doc(self.test_dir)
        self.assertIsNotNone(cached)
        self.assertEqual(cached['documentation'], doc_content)
        self.assertEqual(cached['metadata']['test'], True)

        # Verify cache invalidation
        self.cache.invalidate_cache(self.test_dir)
        cached = self.cache.get_cached_doc(self.test_dir)
        self.assertIsNone(cached)

        # Test cache expiration
        with mock.patch('time.time', return_value=time.time() + 25 * 60 * 60):
            self.cache.cache_doc(self.test_dir, doc_content, metadata)
            cached = self.cache.get_cached_doc(self.test_dir)
            self.assertIsNone(cached)

    def test_context_provision(self):
        """Test context retrieval"""
        # Get context for main.py
        main_path = os.path.join(self.test_dir, "main.py")
        context = self.context.get_context_for_file(main_path)

        # Verify imports are detected
        self.assertIn('utils', context['relationships']['imports'])
        self.assertIn('models.User', context['relationships']['imports'])

        # Verify function detection
        self.assertIn('main', context['relationships']['functions'])

        # Verify related files
        related_files = context['relationships']['related_files']
        self.assertTrue(any('utils.py' in f for f in related_files))
        self.assertTrue(any('models.py' in f for f in related_files))

        # Test edit impact analysis
        edit = """
def new_function():
    user = User()
    return user.get_data()
"""
        impact = self.context.analyze_edit_impact(main_path, edit)

        # Verify impact analysis
        self.assertIn('new_function', impact['modified_elements']['functions'])
        self.assertIn('user', impact['modified_elements']['variables'])
        self.assertEqual(impact['risk_level'], 'low')

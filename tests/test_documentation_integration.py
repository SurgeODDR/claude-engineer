import os
import tempfile
import shutil
from unittest import TestCase
from tools.documentation.handler import DocumentationHandler
from tools.documentation.generator import DocumentationGenerator
from tools.documentation.cache import DocumentationCache
from tools.documentation.context import ContextProvider

class TestDocumentationIntegration(TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.test_dir))

        # Create test repository structure
        self.create_test_repository()

        # Initialize handler
        self.handler = DocumentationHandler()

    def create_test_repository(self):
        """Create a test repository with multiple files and relationships"""
        # Create .git directory to simulate repository
        os.makedirs(os.path.join(self.test_dir, ".git"))

        # Create main application file
        app_content = """
from database import Database
from models import User
from utils import format_response

class Application:
    def __init__(self):
        self.db = Database()
        self.user = None

    def process_request(self, user_id: int):
        self.user = User(user_id)
        data = self.db.get_user_data(user_id)
        return format_response(data)
"""
        self.create_file("app.py", app_content)

        # Create database module
        db_content = """
class Database:
    def get_user_data(self, user_id: int):
        return {'id': user_id, 'name': 'Test User'}
"""
        self.create_file("database.py", db_content)

        # Create models module
        models_content = """
class User:
    def __init__(self, user_id: int):
        self.id = user_id
        self.data = None
"""
        self.create_file("models.py", models_content)

        # Create utils module
        utils_content = """
def format_response(data):
    return {
        'status': 'success',
        'data': data
    }
"""
        self.create_file("utils.py", utils_content)

    def create_file(self, name: str, content: str):
        """Helper to create test files"""
        path = os.path.join(self.test_dir, name)
        with open(path, 'w') as f:
            f.write(content.strip())

    def test_complete_workflow(self):
        """Test complete documentation workflow"""
        app_path = os.path.join(self.test_dir, "app.py")

        # Step 1: Initial documentation generation
        result = self.handler.handle_file_edit(app_path)
        self.assertNotIn('error', result)
        self.assertIn('documentation', result)
        self.assertIn('context', result)

        # Verify tree structure
        self.assertIn('app.py', result['documentation']['tree'])
        self.assertIn('database.py', result['documentation']['tree'])
        self.assertIn('models.py', result['documentation']['tree'])
        self.assertIn('utils.py', result['documentation']['tree'])

        # Verify file contents
        contents = result['documentation']['contents']
        self.assertIn('class Application:', contents)
        self.assertIn('class Database:', contents)
        self.assertIn('class User:', contents)
        self.assertIn('def format_response', contents)

        # Step 2: Verify caching
        cached_result = self.handler.handle_file_edit(app_path)
        self.assertEqual(
            cached_result['documentation'],
            result['documentation'],
            "Cached documentation should match original"
        )

        # Step 3: Test context analysis
        context = cached_result['context']
        self.assertIn('database.py', str(context['relationships']['related_files']))
        self.assertIn('models.py', str(context['relationships']['related_files']))
        self.assertIn('utils.py', str(context['relationships']['related_files']))

        # Step 4: Test edit impact analysis
        edit = """
    def new_method(self):
        user_data = self.db.get_user_data(self.user.id)
        return format_response(user_data)
"""
        result_with_edit = self.handler.handle_file_edit(app_path, edit)
        self.assertIn('impact', result_with_edit)
        impact = result_with_edit['impact']

        # Verify impact analysis
        self.assertIn('new_method', str(impact['modified_elements']))
        self.assertTrue(
            any('database.py' in f for f in impact['affected_files']),
            "Should detect database.py as affected"
        )
        self.assertTrue(
            any('utils.py' in f for f in impact['affected_files']),
            "Should detect utils.py as affected"
        )

        # Step 5: Test documentation refresh
        self.handler.refresh_documentation(self.test_dir)
        refreshed_result = self.handler.handle_file_edit(app_path)
        self.assertEqual(
            refreshed_result['documentation']['tree'],
            result['documentation']['tree'],
            "Refreshed documentation should maintain structure"
        )

        # Step 6: Test chunk-based access
        chunk = self.handler.get_documentation_chunk(self.test_dir, 0)
        self.assertIsNotNone(chunk)
        self.assertIn('File:', chunk)

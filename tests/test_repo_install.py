import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_repo_skills', ROOT/'scripts/install_repo_skills.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class RepositoryInstallTests(unittest.TestCase):
    def fixture(self, root):
        source = root/'skills'/'example'
        source.mkdir(parents=True)
        (source/'SKILL.md').write_text('example')
        return source

    def test_fresh_install_is_relative_idempotent_and_checkable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'Missing'): installer.install(root, check=True)
            self.assertEqual(installer.install(root), ['example'])
            link=root/'.agents/skills/example'
            self.assertEqual(link.readlink(), Path('../../skills/example'))
            self.assertEqual(link.resolve(),source)
            installer.install(root);installer.install(root,check=True)

    def test_does_not_replace_existing_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            link=root/'.agents/skills/example';link.parent.mkdir(parents=True);link.write_text('mine')
            with self.assertRaisesRegex(ValueError,'left unchanged'):installer.install(root)
            self.assertEqual(link.read_text(),'mine')

    def test_rejects_external_discovery_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            outside=root/'elsewhere';outside.mkdir();(root/'.agents').symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'symlink discovery'):installer.install(root)
            self.assertEqual(list(outside.iterdir()),[])

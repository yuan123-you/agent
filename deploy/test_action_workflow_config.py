"""Release wiring gates; no container/service startup and no secret interpolation."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]

class NativeApprovalConfigTest(unittest.TestCase):
    def test_both_services_share_a_default_off_flag_and_durable_ai_volume(self):
        for relative in ('docker-compose.yml','deploy/compose.production.yml'):
            with self.subTest(compose=relative):
                config=yaml.safe_load((ROOT/relative).read_text(encoding='utf-8'))
                for name in ('ai-service','backend'):
                    self.assertEqual(config['services'][name]['environment']['ACTION_WORKFLOWS_ENABLED'],
                                     '${ACTION_WORKFLOWS_ENABLED:-false}')
                volumes=config['services']['ai-service'].get('volumes',[])
                self.assertIn('ai-service-data:/app/data',volumes)
                self.assertIn('ai-service-data',config['volumes'])

    def test_approval_checkpoint_data_never_enters_the_ai_image(self):
        ignored=(ROOT/'ai-service/.dockerignore').read_text(encoding='utf-8').splitlines()
        for pattern in ('data/','*.db','*.db-wal','*.db-shm','*.sqlite*'):
            self.assertIn(pattern,ignored)

    def test_approval_persistence_dependencies_are_pinned(self):
        requirements=(ROOT/'ai-service/requirements.txt').read_text(encoding='utf-8')
        self.assertIn('langgraph-checkpoint-sqlite==3.1.2',requirements)
        self.assertIn('aiosqlite==0.22.1',requirements)

if __name__=='__main__':unittest.main()

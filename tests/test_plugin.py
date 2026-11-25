import json, pathlib, subprocess, tomllib, unittest
R = pathlib.Path(__file__).resolve().parents[1]
class PluginTests(unittest.TestCase):
    def test_packages_are_complete(self):
        originals = list((R/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(originals), 18)
        for skill in originals:
            self.assertRegex(skill.parent.name, r'^vibeops-(?:[a-z0-9]+-)+[a-z0-9]+$')
            self.assertIn('name: ' + skill.parent.name, skill.read_text().split('---', 2)[1].splitlines())
        roles = json.loads((R/'config/role-skills.json').read_text())
        self.assertEqual(roles['plugin'], 'pns-vibeops-plug')
        for metadata in ('.codex-plugin', '.claude-plugin'):
            manifest=json.loads((R/metadata/'plugin.json').read_text())
            self.assertEqual(manifest['name'], roles['plugin'])
            self.assertTrue((R/manifest.get('skills','./skills')).is_dir())
        for registry in ('.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json'):
            marketplace=json.loads((R/registry).read_text())
            self.assertEqual(marketplace['name'], roles['plugin'])
            entry=marketplace['plugins'][0]
            self.assertEqual(entry['name'], roles['plugin'])
            source=entry['source']
            path=source['path'] if isinstance(source,dict) else source
            self.assertEqual((R/path).resolve(),R)
        config=json.loads((R/'hooks/hooks.json').read_text())
        self.assertIn('SessionStart',config['hooks'])
        result=subprocess.run(['sh',str(R/'hooks/session-start.sh')],input='{}',text=True,capture_output=True,timeout=3,cwd='/tmp')
        self.assertEqual(result.returncode,0)
        self.assertIn('sdlc-progress.md',result.stdout)
        self.assertFalse((R/'plugins').exists())
    def test_roles(self):
        files=list((R/'.codex/agents').glob('*.toml'))
        self.assertEqual(len(files),12)
        for p in files:
            role=tomllib.loads(p.read_text())
            self.assertTrue(role['name'].startswith('vibeops-'))
            self.assertEqual(p.stem, role['name'])
            for key in ('name','description','developer_instructions','model','model_reasoning_effort'):self.assertTrue(role[key])
        self.assertEqual(len(list((R/'agents').glob('*.md'))),12)
    def test_no_runtime(self):
        self.assertFalse((R/'sdlc_agent').exists())
        self.assertFalse((R/'pyproject.toml').exists())
        for p in (R/'skills').rglob('*'):
            if p.is_file() and p.suffix not in (".pyc",):
                for obsolete in ('pip install', 'sdlc-agent run', 'scripts/sdlc.py', 'runtime is optional'):
                    self.assertNotIn(obsolete,p.read_text())

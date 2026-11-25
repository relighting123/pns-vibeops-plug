"""Generate host role definitions from reviewed role scopes; not an access gateway."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(root=ROOT):
    config = json.loads((root/'config/role-skills.json').read_text())
    skills = {p.parent.name for p in (root/'skills').glob('*/SKILL.md')}
    output = {}
    for key, role in config['roles'].items():
        selected = [role['stage'], *role['data_skills']]
        if len(selected) != len(set(selected)) or not set(selected) <= skills:
            raise ValueError('Unknown or duplicate selected skill in role ' + key)
        if 'Skill' in role['tools']:
            raise ValueError('Dynamic Skill invocation must be excluded in scoped roles')
        stage = (root/'skills'/role['stage']/'SKILL.md').read_text().split('---', 2)[2].strip()
        if key == 'review':
            stage = stage.replace('in artifacts/review.md', 'in a report returned to the parent (the parent saves artifacts/review.md)')
        instructions = stage + '\n\nRole skill scope: ' + ', '.join(selected) + '.\n'
        instructions += ('Use only these plugin procedures. Do not load other plugin skills or execute their scripts, '
                         'and do not ask the parent to bypass this scope. Receive out-of-scope evidence as task input. '
                         'External data modifications are not assigned to this role. '
                         'Check the assigned output against its completion criteria before reporting. Return requirement IDs, changed paths, exact checks/results, findings, blockers and next action directly to the assigning orchestrator. '
                         'Do not delegate further unless explicitly requested.\n')
        if role['data_skills']:
            instructions += ('Claude receives the selected procedures as preloaded context. '
                             'In Codex, read only the selected SKILL.md files from the installed plugin directory '
                             'when relevant. Never infer database targets, endpoints or credentials.\n')
        else:
            instructions += 'Use supplied external evidence; do not call the plugin data-access clients.\n'
        instructions += ('These instructions and host skill settings do not isolate files, shell commands, '
                         'network access or credentials. Follow actual host and service permissions.\n')
        for tier, profile in config['models'].items():
            default = tier == role['default_tier']
            suffix = '' if default else '-' + tier
            name = role['name'] + suffix
            description = role['description'] + ' Workload: ' + tier + '.'
            yaml = ('---\nname: ' + name + '\ndescription: ' + json.dumps(description)
                    + '\nmodel: ' + profile['claude'] + '\ntools: ' + ', '.join(role['tools']) + '\nskills:\n')
            yaml += ''.join('  - '+json.dumps(config['plugin']+':'+skill)+'\n' for skill in selected)
            output[root/'agents'/f'{key}{suffix}.md'] = yaml + '---\n\n' + instructions
            fields = dict(name=name, description=description, model=profile['codex'],
                          model_reasoning_effort=profile['effort'], developer_instructions=instructions)
            output[root/'.codex/agents'/f'{name}.toml'] = ''.join(
                field + ' = ' + json.dumps(value) + '\n' for field, value in fields.items())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true',help='Update generated files; default checks for drift')
    args=parser.parse_args()
    changed=[]
    for path, content in render().items():
        if not path.exists() or path.read_text()!=content:
            changed.append(str(path.relative_to(ROOT)))
            if args.write:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(content)
    print(json.dumps({'ok':not changed or args.write,'changed':changed,'write':args.write}))
    return 0 if not changed or args.write else 1


if __name__=='__main__':
    raise SystemExit(main())

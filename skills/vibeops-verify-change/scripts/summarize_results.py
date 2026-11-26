"""Render quantitative verification results from reviewed scenario evidence."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


REVIEW_STATES = ('ready', 'rejected', 'missing')
RESULT_STATES = ('passed', 'failed', 'blocked', 'unverified')


def percentage(count, total):
    return f'{count}/{total} ({count / total:.1%})' if total else '0/0 (N/A)'


def summarize(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Provide at least one required scenario')
    reviews = Counter()
    results = Counter()
    requirements = defaultdict(list)
    scenarios = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each scenario must be an object')
        requirement = row.get('requirement')
        scenario = row.get('scenario')
        if not all(isinstance(value, str) and value.strip() for value in (requirement, scenario)):
            raise ValueError('Requirement and scenario IDs are required')
        if scenario in scenarios:
            raise ValueError(f'Duplicate scenario {scenario}')
        review, result = row.get('review'), row.get('result')
        if review not in REVIEW_STATES or result not in RESULT_STATES:
            raise ValueError(f'Invalid review or result state for {scenario}')
        if result in ('passed', 'failed'):
            evidence = row.get('evidence')
            if review != 'ready' or not isinstance(evidence, str) or not evidence.strip():
                raise ValueError(f'Executed scenario {scenario} needs a ready case and evidence')
        scenarios.add(scenario)
        reviews[review] += 1
        results[result] += 1
        requirements[requirement].append(result)

    executed = results['passed'] + results['failed']
    passed_requirements = sum(all(result == 'passed' for result in outcomes)
                              for outcomes in requirements.values())
    return '\n'.join([
        '### Quantitative verification',
        '',
        '| Metric | Result |',
        '|---|---:|',
        f"| Case review | {reviews['ready']} ready / {reviews['rejected']} rejected / {reviews['missing']} missing |",
        f"| Outcomes | {results['passed']} passed / {results['failed']} failed / "
        f"{results['blocked']} blocked / {results['unverified']} unverified |",
        f"| Execution coverage | {percentage(executed, len(scenarios))} |",
        f"| Pass rate (executed) | {percentage(results['passed'], executed)} |",
        f"| Requirements fully passed | {percentage(passed_requirements, len(requirements))} |",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    try:
        report = summarize(json.loads(args.results.read_text(encoding='utf-8')))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(report)


if __name__ == '__main__':
    main()

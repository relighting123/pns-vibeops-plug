"""Compare paired first submissions. Usage: python scripts/compare_skill_runs.py runs.json

Input is an array with one row per representative request. Example shape:
{"request":"A-only intake","cases":["non-A","HOLD"],
 "baseline":{"accepted":false,"questions":2,"passed":["non-A"]},
 "candidate":{"accepted":true,"questions":1,"passed":["non-A","HOLD"]}}

Freeze cases before the runs. Use identical request, code, model and scripted
answers in isolated sessions. Count individual questions presented to a human.
Blind-review the first submitted artifact against the same rubric before fixes.
Set accepted true only if that submission requires no correction. Record actual
passed case IDs; unverified cases count in the denominator. Retain transcripts.
"""
import argparse
import json
from pathlib import Path


def summarize(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Paired requests required')
    totals = {}
    for variant in ('baseline', 'candidate'):
        accepted = questions = passed = possible = 0
        seen = set()
        for row in rows:
            request = row['request']
            cases = row['cases']
            run = row[variant]
            successes = run['passed']
            if not request or request in seen:
                raise ValueError('Request IDs must be unique')
            seen.add(request)
            if not all(isinstance(ids, list) and len(ids) == len(set(ids))
                       and all(isinstance(i, str) and i for i in ids) for ids in (cases, successes)):
                raise ValueError('Expected unique scenario IDs')
            if not set(successes) <= set(cases) or type(run['accepted']) is not bool:
                raise ValueError('Invalid review evidence')
            if type(run['questions']) is not int or run['questions'] < 0:
                raise ValueError('Expected nonnegative question count')
            accepted += run['accepted']
            questions += run['questions']
            passed += len(successes)
            possible += len(cases)
        totals[variant] = dict(requests=len(rows), first_pass_rate=accepted / len(rows),
                               questions=questions, questions_per_request=questions / len(rows),
                               exceptions_passed=passed, exceptions_expected=possible)
    return totals


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.runs.read_text(encoding='utf-8'))), indent=2))

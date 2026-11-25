"""Read a bounded ITSM view for the requirements agent."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'shared/python'))

from itsm_handoff import oldest_first, validate_requests
from oracle_client.connections import load_profile
from oracle_client.query_executor import run_batch


def load_requests(config):
    profile = load_profile(config['oracle_config'], config['database'])
    result, = run_batch(profile, [{
        'action': 'query', 'query': config['query'], 'binds': config.get('binds', {}),
        'max_rows': config['batch_size'],
    }])['results']
    if result['truncated']:
        raise ValueError('ITSM query must page within the configured row and byte limits')
    columns = [column.lower() for column in result['columns']]
    fields = {'request_id', 'revision', 'title', 'summary'}
    if len(columns) != len(set(columns)) or set(columns) - {"target_system", "component", "created_at"} != fields:
        raise ValueError('Expected REQUEST_ID, REVISION, TITLE, SUMMARY columns')
    requests = [dict(zip(columns, row, strict=True)) for row in result['rows']]
    rows = validate_requests(requests, config["batch_size"])
    return oldest_first(rows) if config.get("oldest_first") or "created_at" in columns else rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if os.environ.get("SDLC_DATA_ROLE") != "requirements":
        parser.error("Expected requirements role")
    if type(config["batch_size"]) is not int or not 1 <= config["batch_size"] <= 100:
        parser.error("Invalid batch size")
    rows = load_requests(config)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(rows, out, ensure_ascii=False)

#!/usr/bin/env python
"""
Fetch counts of assays run at contract research sites (Bienta/Enamine and Weizmann) during the reporting
period from the ASAP Discovery CDD Vault, for the RPPR assay statistics (see generate-rppr.py).

Usage (from rppr/):
    python fetch-cdd-assays.py [--period-start 2025-09-19] [--period-end 2026-12-31] [--vault-id 6890]

The API key is read from rppr/CDD_VAULT_API_KEY (a single line `CDD_VAULT_API_KEY=<key>`; gitignored).
It is only sent in the X-CDD-Token request header and is never printed or written anywhere.

No chemical structure information is requested or stored: every batch request passes no_structures=true,
responses are reduced immediately to a whitelist of fields (molecule name, batch program_code), and the script
aborts if a structure field ever appears in a response.

Writes (gitignored, private vault data):
    cdd-data/cdd-assay-measurements.csv  one row per compound measurement (a compound tested in one run;
                                         dose-response points and replicates within a run are collapsed)
    cdd-data/cdd-assay-summary.csv       site x protocol x program_code counts
"""

import argparse
import csv
import datetime
import os
import re
import sys
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, 'CDD_VAULT_API_KEY')
OUTPUT_DIR = os.path.join(HERE, 'cdd-data')
API = 'https://app.collaborativedrug.com/api/v1'
DEFAULT_VAULT_ID = 6890  # ASAP Discovery Vault
DEFAULT_PERIOD_START = '2025-09-19'
DEFAULT_PERIOD_END = '2026-12-31'

SITE_PATTERNS = [('Weizmann', re.compile(r'weizmann', re.I)),
                 ('Bienta/Enamine', re.compile(r'bienta|enamine', re.I))]
EXCLUDE_PATTERN = re.compile(r'^(QC|logistics)_', re.I)  # non-assay protocols (chemical QC, inventory)
STRUCTURE_KEYS = {'smiles', 'cxsmiles', 'inchi', 'inchi_key', 'molfile', 'iupac_name', 'formula',
                  'molecular_formula', 'structure', 'image', 'images', 'svg', 'exact_mass',
                  'molecular_weight', 'formula_weight'}
PAGE_SIZE = 1000
BATCH_CHUNK = 200


class CDDError(RuntimeError):
    pass


def load_key():
    if not os.path.exists(KEY_FILE):
        sys.exit(f'API key file not found: {KEY_FILE} (expected a line CDD_VAULT_API_KEY=<key>)')
    match = re.search(r'^\s*CDD_VAULT_API_KEY\s*=\s*(\S+)', open(KEY_FILE).read(), re.M)
    if not match:
        sys.exit(f'{KEY_FILE} does not contain a line CDD_VAULT_API_KEY=<key>')
    return match.group(1)


class Vault:
    def __init__(self, vault_id, key):
        self.base = f'{API}/vaults/{vault_id}'
        self.session = requests.Session()
        self.session.headers['X-CDD-Token'] = key

    def get(self, path, **params):
        try:
            response = self.session.get(self.base + path, params=params, timeout=300)
        except requests.RequestException as e:
            # Never surface the request (headers contain the key)
            raise CDDError(f'Request to {path} failed: {type(e).__name__}') from None
        if not response.ok:
            raise CDDError(f'GET {path} returned HTTP {response.status_code}')
        return response.json()

    def paginate(self, path, **params):
        offset = 0
        while True:
            page = self.get(path, offset=offset, page_size=PAGE_SIZE, **params)
            objects = page.get('objects', [])
            yield from objects
            offset += len(objects)
            if not objects or offset >= page.get('count', 0):
                break


def assert_no_structures(obj, where):
    """Abort (without printing values) if any structure field is present anywhere in obj."""
    if isinstance(obj, dict):
        found = STRUCTURE_KEYS & set(k for k, v in obj.items() if v not in (None, '', []))
        found.discard('formula_weight')  # numeric batch property; dropped by the whitelist below
        if found:
            sys.exit(f'ABORT: structure field(s) {sorted(found)} present in {where} response; nothing written')
        for value in obj.values():
            assert_no_structures(value, where)
    elif isinstance(obj, list):
        for value in obj:
            assert_no_structures(value, where)


def site_of(protocol_name):
    for site, pattern in SITE_PATTERNS:
        if pattern.search(protocol_name):
            return site
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--vault-id', type=int, default=DEFAULT_VAULT_ID)
    parser.add_argument('--period-start', default=DEFAULT_PERIOD_START)
    parser.add_argument('--period-end', default=DEFAULT_PERIOD_END)
    parser.add_argument('--limit-protocols', type=int, default=None, help='only fetch the first N protocols (testing)')
    args = parser.parse_args()
    start = datetime.date.fromisoformat(args.period_start)
    end = datetime.date.fromisoformat(args.period_end)

    vault = Vault(args.vault_id, load_key())

    # 1. Protocols run at the contract sites, with runs in the period
    selected = []
    for protocol in vault.paginate('/protocols'):
        name = protocol.get('name', '')
        site = site_of(name)
        if not site or EXCLUDE_PATTERN.search(name):
            continue
        runs = {run['id']: run['run_date'] for run in protocol.get('runs') or []
                if run.get('run_date') and start <= datetime.date.fromisoformat(run['run_date'][:10]) <= end}
        if runs:
            selected.append({'id': protocol['id'], 'name': name, 'site': site, 'runs': runs,
                             'description': ' '.join((protocol.get('description') or '').split())})
    selected.sort(key=lambda p: (p['site'], p['name']))
    if args.limit_protocols:
        selected = selected[:args.limit_protocols]
    print(f'{len(selected)} contract-site protocols with runs between {start} and {end}')

    # 2. Readout rows (one per compound measurement) for in-period runs
    measurements = []
    for protocol in selected:
        n_rows, n_no_batch = 0, 0
        run_ids = sorted(protocol['runs'])
        for i in range(0, len(run_ids), 50):
            chunk = run_ids[i:i + 50]
            for row in vault.paginate('/readout_rows', protocols=protocol['id'], runs=','.join(map(str, chunk))):
                if row.get('run') not in protocol['runs']:
                    continue
                n_rows += 1
                if not row.get('batch'):
                    n_no_batch += 1
                    continue
                measurements.append({'protocol': protocol, 'run_id': row['run'], 'batch_id': row['batch']})
        protocol['rows_without_batch'] = n_no_batch
        print(f'  {protocol["site"]:15s} {protocol["name"]}: {n_rows} rows in {len(protocol["runs"])} runs'
              + (f' ({n_no_batch} without a compound batch, excluded)' if n_no_batch else ''))

    # 3. Resolve batches -> CDD number (molecule name) and program_code, without structures
    batch_info = {}
    batch_ids = sorted({m['batch_id'] for m in measurements})
    for i in range(0, len(batch_ids), BATCH_CHUNK):
        chunk = batch_ids[i:i + BATCH_CHUNK]
        for batch in vault.paginate('/batches', batches=','.join(map(str, chunk)), no_structures='true'):
            assert_no_structures(batch, '/batches')
            molecule = batch.get('molecule') or {}
            batch_info[batch['id']] = {
                'cdd_number': molecule.get('name', ''),
                'program_code': ((batch.get('batch_fields') or {}).get('program_code') or '').strip(),
            }
    print(f'Resolved {len(batch_info)}/{len(batch_ids)} batches')

    # 4. Collapse readout rows (dose-response points, replicates) to one measurement per compound per run
    collapsed = {}
    for m in measurements:
        protocol = m['protocol']
        info = batch_info.get(m['batch_id'], {'cdd_number': '', 'program_code': ''})
        key = (protocol['id'], m['run_id'], info['cdd_number'] or f'batch:{m["batch_id"]}', info['program_code'])
        if key not in collapsed:
            collapsed[key] = {'cdd_number': info['cdd_number'], 'site': protocol['site'], 'protocol': protocol['name'],
                              'protocol_id': protocol['id'], 'run_id': m['run_id'],
                              'run_date': protocol['runs'][m['run_id']][:10], 'program_code': info['program_code'],
                              'readout_rows': 0, 'protocol_description': protocol['description']}
        collapsed[key]['readout_rows'] += 1
    rows = sorted(collapsed.values(), key=lambda r: (r['site'], r['protocol'], r['run_date'], r['cdd_number']))

    # 5. Write outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fields = ['cdd_number', 'site', 'protocol', 'protocol_id', 'run_id', 'run_date', 'program_code', 'readout_rows',
              'protocol_description']
    summary = defaultdict(lambda: {'measurements': 0, 'readout_rows': 0, 'compounds': set(), 'runs': set()})
    with open(os.path.join(OUTPUT_DIR, 'cdd-assay-measurements.csv'), 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
            s = summary[(r['site'], r['protocol'], r['program_code'])]
            s['measurements'] += 1
            s['readout_rows'] += r['readout_rows']
            s['compounds'].add(r['cdd_number'])
            s['runs'].add(r['run_id'])
    bad_names = sum(1 for r in rows if not re.match(r'^ASAP-\d+$', r['cdd_number']))
    with open(os.path.join(OUTPUT_DIR, 'cdd-assay-summary.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['site', 'protocol', 'program_code', 'measurements', 'unique_compounds', 'runs', 'readout_rows'])
        for (site, name, code), s in sorted(summary.items()):
            writer.writerow([site, name, code, s['measurements'], len(s['compounds']), len(s['runs']), s['readout_rows']])

    print(f'Wrote {len(rows)} compound measurements ({len(measurements)} readout rows) to {os.path.relpath(OUTPUT_DIR)}/')
    if bad_names:
        print(f'WARNING: {bad_names} measurements have a CDD number not matching ASAP-NNNNNNN')
    missing = sum(1 for r in rows if not r['program_code'])
    if missing:
        print(f'WARNING: {missing} measurements have no program_code batch field')


if __name__ == '__main__':
    try:
        main()
    except CDDError as e:
        sys.exit(f'CDD Vault API error: {e}')

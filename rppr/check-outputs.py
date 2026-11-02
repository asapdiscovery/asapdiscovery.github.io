#!/usr/bin/env python
"""
Audit reportable outputs against the Hugo YAML data files (read-only).

1. Extracts hyperlinks from a slide deck PDF (default: outputs-overview-slides.pdf) and checks that each
   one is represented somewhere in ../data (publications, outputs, TEPs).
2. For every publication in ../data/publications/publications.yaml, queries bioRxiv / Crossref for the
   preprint posting date, version history, and published version, and flags discrepancies.
3. Flags outputs whose project/core attribution does not match a component in specific-aims.yaml.

Writes a Markdown report (default: outputs/outputs-audit.md).

Usage:
    python check-outputs.py [--slides outputs-overview-slides.pdf] [--report outputs/outputs-audit.md] [--offline]
"""
import argparse
import datetime
import glob
import os
import re
import sys
import time

import requests
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')

DOI_RE = re.compile(r'(10\.\d{4,9}/[^\s"\'<>)\]]+)', re.I)
PMC_RE = re.compile(r'(PMC\d+)', re.I)
PMID_RE = re.compile(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', re.I)
GITHUB_RE = re.compile(r'github\.com/([^/\s?#]+/[^/\s?#]+)', re.I)

session = requests.Session()
session.headers['User-Agent'] = 'asapdiscovery-rppr-audit/1.0 (mailto:john.chodera@choderalab.org)'


def get_json(url, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                print(f'  WARNING: {url}: {e}', file=sys.stderr)
                return None
            time.sleep(2)


def strip_doi_version(doi):
    """Normalize a DOI: lowercase, drop trailing punctuation and bioRxiv/chemRxiv version suffixes."""
    doi = doi.lower().rstrip('.,;')
    doi = re.sub(r'(\.full(\.pdf)?|\.abstract)$', '', doi)
    doi = re.sub(r'v\d+$', '', doi)          # bioRxiv: 2024.04.29.591650v1
    doi = re.sub(r'-v\d+$', '', doi)         # chemRxiv: chemrxiv-2025-zd9mr-v5
    return doi


def doi_version(doi):
    m = re.search(r'-?v(\d+)$', doi.lower().rstrip('.,;'))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------------------------------------
# Identifier resolution
# ---------------------------------------------------------------------------------------------------------

def idconv(identifier):
    """Resolve a PMCID or PMID to {doi, pmcid, pmid} via the NCBI ID converter."""
    js = get_json(f'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={identifier}&format=json')
    if not js or not js.get('records'):
        return {}
    rec = js['records'][0]
    return {k: rec.get(k) for k in ('doi', 'pmcid', 'pmid')}


def esummary_pmid(pmid):
    """Fallback for PMIDs not in PMC: get DOI and title via E-utilities."""
    js = get_json(f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json')
    try:
        rec = js['result'][str(pmid)]
    except (TypeError, KeyError):
        return {}
    doi = next((a['value'] for a in rec.get('articleids', []) if a['idtype'] == 'doi'), None)
    return {'doi': doi, 'title': rec.get('title')}


def crossref(doi):
    js = get_json(f'https://api.crossref.org/works/{doi}')
    return js['message'] if js else None


def crossref_date(msg, *keys):
    for key in keys:
        if msg and key in msg and msg[key].get('date-parts'):
            parts = msg[key]['date-parts'][0]
            parts = parts + [1] * (3 - len(parts))
            return datetime.date(*parts)
    return None


def biorxiv_details(doi):
    """Return list of versions [{version, date, published}] from the bioRxiv API, or None."""
    for server in ('biorxiv', 'medrxiv'):
        js = get_json(f'https://api.biorxiv.org/details/{server}/{doi}')
        if js and js.get('collection'):
            return server, js['collection']
    return None, None


# ---------------------------------------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------------------------------------

def load_yaml_texts():
    texts = {}
    for path in glob.glob(os.path.join(DATA, '**', '*.yaml'), recursive=True):
        with open(path) as f:
            texts[os.path.relpath(path, os.path.join(HERE, '..'))] = f.read().lower()
    return texts


def find_in_yaml(texts, needles):
    hits = []
    for path, text in texts.items():
        if any(n and n.lower() in text for n in needles):
            hits.append(path)
    return hits


def extract_pdf_links(pdf_path):
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    links = {}
    for pageno, page in enumerate(reader.pages, start=1):
        for annot in page.get('/Annots') or []:
            annot = annot.get_object()
            action = annot.get('/A')
            if action and '/URI' in action:
                uri = str(action['/URI']).strip()
                links.setdefault(uri, set()).add(pageno)
    return links


def component_names():
    with open(os.path.join(HERE, 'specific-aims.yaml')) as f:
        return set(yaml.safe_load(f).keys())


# ---------------------------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------------------------

def check_slide_links(pdf_path, texts, offline):
    rows = []
    for uri, pages in sorted(extract_pdf_links(pdf_path).items()):
        needles, note = [], ''
        m = DOI_RE.search(uri)
        if m:
            needles.append(strip_doi_version(m.group(1)))
        m = PMC_RE.search(uri)
        if m:
            needles.append(m.group(1))
            if not offline:
                ids = idconv(m.group(1))
                if ids.get('doi'):
                    needles.append(ids['doi'].lower())
                    note = f"doi:{ids['doi']}"
        m = PMID_RE.search(uri)
        if m:
            needles.append(m.group(1))
            if not offline:
                ids = idconv(m.group(1)) or {}
                if not ids.get('doi'):
                    ids = esummary_pmid(m.group(1))
                if ids.get('doi'):
                    needles.append(ids['doi'].lower())
                    note = f"doi:{ids['doi']}"
                if ids.get('pmcid'):
                    needles.append(ids['pmcid'])
        m = GITHUB_RE.search(uri)
        if m:
            needles.append('github.com/' + m.group(1).lower())
            needles.append(m.group(1).lower())
        if not needles:
            needles.append(uri.split('?')[0].rstrip('/').lower())
        # Elsevier PII links (e.g. Biophys J) — resolve via Crossref is not possible from PII; note it.
        if 'S0006-3495' in uri or 'cell.com' in uri:
            note = (note + ' Elsevier PII link; match by journal DOI manually').strip()
        hits = find_in_yaml(texts, needles)
        rows.append((uri, sorted(pages), hits, note))
    return rows


def check_publications(offline):
    with open(os.path.join(DATA, 'publications', 'publications.yaml')) as f:
        pubs = yaml.safe_load(f)
    issues = []
    for pub in pubs:
        title = pub.get('title', '?')
        short = title[:70]
        pre = pub.get('preprint') or {}
        published = pub.get('published') or {}
        if not (pub.get('projects') or pub.get('cores')):
            issues.append((short, 'No project/core attribution: will not appear in any component report'))
        if offline:
            continue
        m = DOI_RE.search(str(pre.get('url', '')))
        if m:
            raw = m.group(1)
            doi = strip_doi_version(raw)
            recorded_date = pre.get('date')
            recorded_versions = pre.get('versions') or []
            if doi.startswith('10.1101/'):
                server, coll = biorxiv_details(doi)
                if coll:
                    first, latest = coll[0], coll[-1]
                    first_date = datetime.date.fromisoformat(first['date'])
                    latest_date = datetime.date.fromisoformat(latest['date'])
                    if recorded_date != first_date:
                        issues.append((short, f'preprint.date {recorded_date} != {server} v{first["version"]} posted {first_date}'))
                    if int(latest['version']) > 1 and len(recorded_versions) < int(latest['version']):
                        vlist = ', '.join(f"v{c['version']} {c['date']}" for c in coll)
                        issues.append((short, f'{len(coll)} versions on {server} ({vlist}); preprint.versions has {len(recorded_versions)}'))
                    pub_doi = latest.get('published')
                    if pub_doi and pub_doi != 'NA' and not published:
                        issues.append((short, f'{server} reports published version doi:{pub_doi} but no `published:` block'))
                    elif pub_doi and pub_doi != 'NA' and published and published.get('doi', '').lower() != pub_doi.lower():
                        issues.append((short, f"published.doi {published.get('doi')} != {server} published {pub_doi}"))
                else:
                    issues.append((short, f'bioRxiv API has no record for {doi}'))
            elif doi.startswith('10.26434/'):
                # chemRxiv registers one DOI per version: v1 is the unversioned DOI, later ones are -vN.
                versions = []
                for v in range(1, 15):
                    msg = crossref(doi if v == 1 else f'{doi}-v{v}')
                    if not msg:
                        if v > 2:
                            break
                        continue
                    versions.append((v, crossref_date(msg, 'posted', 'created', 'issued')))
                    if v == 1:
                        has_pub = [r['id'] for r in (msg.get('relation') or {}).get('is-preprint-of', [])]
                        if has_pub and not published:
                            issues.append((short, f'chemRxiv reports published version doi:{has_pub[0]} but no `published:` block'))
                if versions:
                    first_v, first_date = versions[0]
                    latest_v, latest_date = versions[-1]
                    if recorded_date != first_date:
                        issues.append((short, f'preprint.date {recorded_date} != chemRxiv v{first_v} posted {first_date}'))
                    rec_v = doi_version(raw)
                    if rec_v and rec_v != latest_v:
                        issues.append((short, f'preprint.url is v{rec_v} but latest chemRxiv version is v{latest_v} ({latest_date})'))
                    if len(versions) > 1 and len(recorded_versions) < len(versions):
                        vlist = ', '.join(f'v{v} {d}' for v, d in versions)
                        issues.append((short, f'{len(versions)} chemRxiv versions ({vlist}); preprint.versions has {len(recorded_versions)}'))
            else:
                msg = crossref(doi)
                if msg:
                    d = crossref_date(msg, 'posted', 'published-online', 'created')
                    if d and recorded_date != d:
                        issues.append((short, f'preprint.date {recorded_date} != Crossref {d}'))
        if published.get('doi'):
            msg = crossref(published['doi'])
            if msg:
                d_online = crossref_date(msg, 'published-online', 'published-print', 'issued')
                if d_online and published.get('date') != d_online:
                    issues.append((short, f"published.date {published.get('date')} != Crossref online {d_online}"))
                for key in ('volume', 'page'):
                    yaml_key = 'pages' if key == 'page' else key
                    if msg.get(key) and not published.get(yaml_key):
                        issues.append((short, f'published.{yaml_key} missing (Crossref: {msg[key]})'))
            else:
                issues.append((short, f"Crossref has no record for published doi {published['doi']}"))
            if not (published.get('pmcid') or published.get('nihmsid')):
                issues.append((short, 'published entry has no pmcid/nihmsid (NIH public access compliance)'))
    return issues


def check_attribution():
    known = component_names()
    with open(os.path.join(HERE, 'component-aliases.yaml')) as f:
        known |= set((yaml.safe_load(f) or {}).keys())
    unknown = {}
    for path in glob.glob(os.path.join(DATA, '**', '*.yaml'), recursive=True):
        with open(path) as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError:
                continue

        def walk(node):
            if isinstance(node, dict):
                for key in ('projects', 'cores'):
                    if isinstance(node.get(key), list):
                        for name in node[key]:
                            if name not in known:
                                unknown.setdefault(name, set()).add(os.path.relpath(path, DATA))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(data)
    return unknown


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--slides', default=os.path.join(HERE, 'outputs-overview-slides.pdf'))
    parser.add_argument('--report', default=os.path.join(HERE, 'outputs', 'outputs-audit.md'))
    parser.add_argument('--offline', action='store_true', help='Skip external API lookups')
    args = parser.parse_args()

    texts = load_yaml_texts()
    out = [f'# Outputs audit ({datetime.date.today()})', '']

    if os.path.exists(args.slides):
        print('Checking slide links...')
        rows = check_slide_links(args.slides, texts, args.offline)
        missing = [r for r in rows if not r[2]]
        out += [f'## Slide links ({len(rows)} total, {len(missing)} not found in YAML)', '',
                '| Status | Link | Slide(s) | Found in | Note |', '|---|---|---|---|---|']
        for uri, pages, hits, note in sorted(rows, key=lambda r: bool(r[2])):
            status = 'OK' if hits else '**MISSING**'
            out.append(f"| {status} | {uri} | {', '.join(map(str, pages))} | {'<br>'.join(hits)} | {note} |")
        out.append('')

    print('Checking publications...')
    issues = check_publications(args.offline)
    out += [f'## Publication metadata issues ({len(issues)})', '', '| Publication | Issue |', '|---|---|']
    out += [f'| {t} | {i} |' for t, i in issues]
    out.append('')

    print('Checking attribution...')
    unknown = check_attribution()
    out += ['## Attribution names not matching specific-aims.yaml components', '',
            '| Name | Files |', '|---|---|']
    out += [f"| {name} | {', '.join(sorted(files))} |" for name, files in sorted(unknown.items())]
    out.append('')

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, 'w') as f:
        f.write('\n'.join(out))
    print(f'Wrote {args.report}')


if __name__ == '__main__':
    main()

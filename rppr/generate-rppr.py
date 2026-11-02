#!/usr/bin/env python
"""
Generate the NIH RPPR (PHS 2590 Form Page 5 continuation) progress reports for the ASAP AViDD U19 Center.

One Word document is produced per Project/Core listed in specific-aims.yaml. Each document combines:

* generated front matter and "A. Specific Aims" (from specific-aims.yaml)
* the narrative "B. Studies and Results", "C. Significance", "D. Plans" sections written by each
  Project/Core in Word documents in a (Google Drive) folder (--drive-sections)
* a generated list of publications, preprints, and research outputs for this component during the
  reporting period, inserted at the end of section B (from the Hugo YAML data in ../data)
* generated compliance sections (Human Subjects, Vertebrate Animals, ...)

Issues found during generation (missing sections, leftover template instructions, unresolved comments,
missing figures, unattributed outputs, ...) are collected in <output-dir>/rppr-issues.md.

Usage:
    python generate-rppr.py [--drive-sections DIR] [--output-dir outputs] [--components "Project 6" ...]
"""

import argparse
import datetime
import glob
import os
import re
import shutil

import docx
import yaml
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: F401 (used by generated render code)
from docx.oxml.ns import qn
from docx.shared import Pt, Cm  # noqa: F401 (used by generated render code)

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DRIVE_SECTIONS = ('/Users/choderaj/Google Drive/Shared drives/ASAP Discovery/unrestricted/'
                          'ASAP administrative core/2026 ASAP RPPR Progress report/'
                          '2026 ASAP Progress Report written components')

# Reporting period (overridable from the command line)
#reporting_period_start = datetime.date.fromisoformat('2022-05-01')
#reporting_period_end = datetime.date.fromisoformat('2023-04-30')
#reporting_period_start = datetime.date.fromisoformat('2023-05-01')
#reporting_period_end = datetime.date.fromisoformat('2024-04-30')
reporting_period_start = datetime.date.fromisoformat('2025-09-19')
reporting_period_end = datetime.date.fromisoformat('2026-12-31')
grant_id = 'NIH U19 AI171399'

DOCX_TEMPLATE = '2590_continuation-template.docx'

# Historical / alternate component names used in the Hugo data, mapped to specific-aims.yaml keys
# (see component-aliases.yaml). Names not listed there and not in specific-aims.yaml are reported as issues.
with open(os.path.join(HERE, 'component-aliases.yaml')) as _f:
    ATTRIBUTION_ALIASES = yaml.safe_load(_f) or {}

# Section headings in the Drive documents (first match of each, in order)
SECTION_PATTERNS = {
    'A': re.compile(r'^A\.\s+Specific\s+Aims', re.I),
    'B': re.compile(r'^B\.\s+(Studies(\s+and\s+Results)?|Results)\b', re.I),
    'C': re.compile(r'^C\.\s+Significance\b', re.I),
    'D': re.compile(r'^(D\.\s+Plans\b|Planned\s+Research\s*$)', re.I),
}
# Headings that end section D (authors sometimes start from a previously generated report that includes
# the compliance sections and an old publication list; those are regenerated, so they are dropped)
END_OF_PLANS_PATTERN = re.compile(r'^(Human Subjects|Publications(\s+and\s+Preprints)?|Project Generated Resources)\s*$', re.I)
# Author-provided "Project Generated Resources" narrative (kept and placed in the generated trailer)
RESOURCES_PATTERN = re.compile(r'^Project Generated Resources\s*$', re.I)
SECTION_TITLES = {
    'A': 'A. Specific Aims',
    'B': 'B. Studies and Results',
    'C': 'C. Significance',
    'D': 'D. Plans',
}

#
# Issue collection
#

ISSUES = []  # list of (component, severity, message)
_seen_issues = set()


def issue(component, message, severity='warning'):
    key = (component, severity, message)
    if key in _seen_issues:
        return
    _seen_issues.add(key)
    ISSUES.append(key)
    print(f'  {severity.upper()} [{component}]: {message}')


#
# Define Markdown to docx renderer
#

import mistune  # noqa: E402


class MathBlockGrammar(mistune.BlockGrammar):
    block_math = re.compile(r"^\$\$(.*?)\$\$", re.DOTALL)


class MathBlockLexer(mistune.BlockLexer):
    default_rules = ['block_math'] + mistune.BlockLexer.default_rules

    def __init__(self, rules=None, **kwargs):
        if rules is None:
            rules = MathBlockGrammar()
        super(MathBlockLexer, self).__init__(rules, **kwargs)

    def parse_block_math(self, m):
        """Parse a $$math$$ block"""
        self.tokens.append({'type': 'block_math', 'text': m.group(1)})


class MarkdownWithMath(mistune.Markdown):
    def __init__(self, renderer, **kwargs):
        kwargs['block'] = MathBlockLexer
        super(MarkdownWithMath, self).__init__(renderer, **kwargs)

    def output_block_math(self):
        return self.renderer.block_math(self.token['text'])


# Generates python-docx code (as a string) that renders the Markdown into `document`
class PythonDocxRenderer(mistune.Renderer):
    def __init__(self, **kwds):
        super(PythonDocxRenderer, self).__init__(**kwds)
        self.table_memory = []
        self.img_counter = 0
        self.list_level_counter = 0

    def header(self, text, level, raw):
        return "p = document.add_heading('', %d)\n" % (level) + text

    def paragraph(self, text):
        if 'add_picture' in text:
            return text
        return '\n'.join(('p = document.add_paragraph()', text)) + '\n'

    def list(self, body, ordered):
        return body + ''

    def list_item(self, text):
        return '\n'.join(("p = document.add_paragraph('', style = 'BasicUserList')", text))

    def table(self, header, body):
        import itertools
        number_cols = header.count('\n') - 2
        number_rows = int(len(self.table_memory) / number_cols)
        cells = ["table.rows[%d].cells[%d].paragraphs[0]%s\n" % (i, j, self.table_memory.pop(0)[1:]) for i, j in itertools.product(range(number_rows), range(number_cols))]
        return '\n'.join(["table = document.add_table(rows=%d, cols=%d, style = 'BasicUserTable')" % (number_rows, number_cols)] + cells) + 'document.add_paragraph().add_run().add_break()\n'

    def table_cell(self, content, **flags):
        self.table_memory.append(content)
        return content

    # SPAN LEVEL
    def text(self, text):
        text = re.sub(r"\s+", r" ", text)
        return "p.add_run(%r)\n" % text

    def emphasis(self, text):
        return text[:-1] + '.italic = True\n'

    def double_emphasis(self, text):
        return text[:-1] + '.bold = True\n'

    def codespan(self, text):
        return "p.add_run(%r, style='CodeSpan')\n" % text

    def block_code(self, code, language):
        return "p = document.add_paragraph()\np.add_run(%r)\np.style = 'BlockCode'\np.add_run().add_break()\n" % code

    def link(self, link, title, content):
        # `content` is already rendered python-docx code (from text/emphasis spans)
        return content + "p.add_run(%r)\n" % f' [{link}]'

    def autolink(self, link, is_email=False):
        return "p.add_run(%r)\n" % link

    def inline_html(self, text):
        return ""

    def image(self, src, title, alt_text):
        return '\n'.join((
            "p = document.add_paragraph()",
            "p.alignment = WD_ALIGN_PARAGRAPH.CENTER",
            "p.space_after = Pt(18)",
            "run = p.add_run()",
            "run.add_picture(%r)" % src if "tmp" in src else "run.add_picture(%r, width=Cm(15))" % src,
            "run.add_break()",
            "run.add_text(%r)" % (alt_text or ''),
            "run.font.italic = True",
            "run.add_break()"
            )) + '\n'

    def hrule(self):
        return "document.add_page_break()\n"

    def block_math(self, text):
        import sympy
        if not os.path.exists('tmp'):
            os.makedirs('tmp')
        filename = 'tmp/tmp%d.png' % self.img_counter
        self.img_counter = self.img_counter + 1
        sympy.preview(r'$$%s$$' % text, output='png', viewer='file', filename=filename, euler=False)
        return self.image(filename, None, "Equation " + str(self.img_counter - 1))


def render_markdown(document, markdown_text):
    """Render Markdown text into the given python-docx Document."""
    if not markdown_text.strip():
        return document
    renderer = PythonDocxRenderer()
    render_code = MarkdownWithMath(renderer=renderer)(markdown_text)
    exec(render_code, globals(), {'document': document})
    return document


def new_document():
    """Create an empty document from the continuation template (styles, header, footer preserved)."""
    document = docx.Document(DOCX_TEMPLATE)
    body = document.element.body
    for child in list(body):
        if child.tag != qn('w:sectPr'):
            body.remove(child)
    return document


#
# Data loading helpers
#

def load_yaml(yaml_filename):
    with open(yaml_filename, 'r') as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


get_components = load_yaml  # backwards compatibility


def normalize_component(name):
    return ATTRIBUTION_ALIASES.get(name, name)


def contributors(output):
    names = [normalize_component(n) for n in (output.get('projects') or []) + (output.get('cores') or [])]
    return list(dict.fromkeys(names))  # de-duplicate (aliases can map two names to one component), keep order


def component_contributed_to_output(component_shortname, output):
    """Return True if specified component contributed to this research output"""
    return component_shortname in contributors(output)


def to_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value).strip())


def text_date_is_in_reporting_period(text_date):
    """Return True if text date is in event reporting period"""
    return reporting_period_start <= to_date(text_date) <= reporting_period_end


def filter_events_to_reporting_period(output, source=''):
    """
    Remove events not in reporting period.

    Return True if at least one event remains; else False
    """
    if 'events' not in output:
        issue('data', f'No events listed for output "{output.get("name")}" in {source}; it cannot be reported', 'info')
        return False
    events = [event for event in output['events'] if text_date_is_in_reporting_period(event['date'])]
    output['events'] = events
    return len(events) > 0


#
# Output rendering (Markdown)
#

def render_products_to_markdown(yaml_filepath, component_shortname):
    """
    Render list of products with dated `events` to Markdown from a given YAML file.
    """
    outputs = load_yaml(yaml_filepath)
    source = os.path.basename(yaml_filepath)
    if hasattr(outputs, 'items'):
        outputs = list(outputs.values())

    markdown_text = ""
    for output in outputs:
        if not component_contributed_to_output(component_shortname, output):
            continue
        if not filter_events_to_reporting_period(output, source):
            continue

        markdown_text += f"**{output['name']}**"
        if output.get('status', None) == 'draft':
            markdown_text += ' [DRAFT]'
        markdown_text += '\n\n'

        if 'description' in output:
            markdown_text += f"{str(output['description']).strip()}\n\n"

        if 'permalink' in output:
            markdown_text += f"{output['permalink']}\n\n"
        elif output.get('links'):
            for link in output['links']:
                markdown_text += f"* _{link['name']}_: {link['url']}\n"
            markdown_text += '\n'
        else:
            issue(component_shortname, f'Output "{output["name"]}" ({source}) has no permalink or links')

        markdown_text += 'Contributing Projects and Cores: ' + ', '.join(contributors(output)) + '\n\n'

        for event in output['events']:
            markdown_text += f"* {event['date']} : {event['description']}\n"
        markdown_text += '\n'

    return markdown_text


def render_research_outputs(component_shortname):
    """Render research outputs (with `events`) for this Project/Core to Markdown."""
    resource_filenames = [
        'targeting_opportunities.yaml',  # project 1
        'circulating_variants.yaml',  # project 1
        'molecules.yaml',  # projects 3, 4, 5
        'TCPs.yaml',  # project 5
        'TPPs.yaml',  # project 6
        'assay_cascades.yaml',  # Projects 3, 4, 5
    ]
    markdown_text = ""
    for resource_filename in resource_filenames:
        resource_filepath = os.path.join('../data/outputs', resource_filename)
        markdown_text += render_products_to_markdown(resource_filepath, component_shortname)
    return markdown_text


def render_software(component_shortname):
    return render_products_to_markdown('../data/outputs/software.yaml', component_shortname)


def render_protocols(component_shortname):
    """Render protocols (dated by `date`) for this Project/Core to Markdown."""
    protocols = load_yaml('../data/outputs/protocols.yaml')
    markdown_text = ''
    for protocol in protocols:
        if not component_contributed_to_output(component_shortname, protocol):
            continue
        if 'date' not in protocol or not text_date_is_in_reporting_period(protocol['date']):
            continue
        line = f"* **{protocol['name']}**"
        if protocol.get('version'):
            line += f" (version {protocol['version']})"
        line += f". {protocol['date']}."
        if protocol.get('url'):
            line += f" {protocol['url']}"
        markdown_text += line + '\n'
    return markdown_text + ('\n' if markdown_text else '')


def render_chembl_datasets(component_shortname):
    """Render ChEMBL dataset deposits publicly released in the reporting period."""
    datasets = load_yaml('../data/outputs/chembl_datasets.yaml')
    markdown_text = ''
    for dataset in datasets:
        if not component_contributed_to_output(component_shortname, dataset):
            continue
        released = dataset.get('released', dataset.get('date'))
        if not released or not text_date_is_in_reporting_period(released):
            continue
        release = str(dataset.get('chembl_release', '')).replace('_', ' ')
        markdown_text += (f"* **{dataset['title']}** ({dataset['chembl_id']}; {dataset.get('category', '')}). "
                          f"Released in {release} on {released}. {dataset.get('doi_url', '')}\n")
    return markdown_text + ('\n' if markdown_text else '')


def render_patents(component_shortname):
    """Render pending patent applications (listed regardless of date while pending)."""
    path = '../data/outputs/patents.yaml'
    if not os.path.exists(path):
        return ''
    markdown_text = ''
    for patent in load_yaml(path) or []:
        if not component_contributed_to_output(component_shortname, patent):
            continue
        status = str(patent.get('status', 'pending'))
        filed = patent.get('filed')
        if status != 'pending' and not (filed and text_date_is_in_reporting_period(filed)):
            continue
        line = f"* **{patent['name']}**. {patent.get('type', 'Patent application')} {patent.get('application', '')}"
        line += f", filed {filed}" if filed else ''
        line += f" ({status}). {str(patent.get('description', '')).strip()}"
        markdown_text += line + '\n'
        if not filed:
            issue(component_shortname, f'Patent application {patent.get("application")} has no filing date in patents.yaml')
    return markdown_text + ('\n' if markdown_text else '')


def render_TEP_outputs(component_shortname):
    """Render TEP resources completed in the reporting period for this Project/Core to Markdown."""
    markdown_text = ""
    seen = set()  # resources shared between TEPs (e.g. pan-flavivirus datasets) are reported once
    for yaml_filename in sorted(glob.glob('../data/outputs/TEPs/*.yaml')):
        TEP = load_yaml(yaml_filename)['TEP']
        for resource in TEP.get('resources') or []:
            key = (resource.get('name'), str(resource.get('date')), str(resource.get('description', '')).strip())
            if key in seen:
                continue
            if 'date' not in resource:
                issue('data', f'TEP resource "{resource.get("name")}" in {os.path.basename(yaml_filename)} has no date', 'info')
                continue
            try:
                in_period = text_date_is_in_reporting_period(resource['date'])
            except ValueError:
                issue('data', f'TEP resource "{resource.get("name")}" in {os.path.basename(yaml_filename)} has invalid date {resource["date"]!r}')
                continue
            if not in_period or not component_contributed_to_output(component_shortname, resource):
                continue
            seen.add(key)

            markdown_text += f"**{resource['name']}**\n\n"
            markdown_text += f"*Date completed:* {resource['date']}\n\n"
            if 'description' in resource:
                markdown_text += f"{str(resource['description']).strip()}\n\n"
            if 'id' in resource:
                markdown_text += f"http://asapdiscovery.org/outputs/target-enabling-packages/#{resource['id']}\n\n"
            elif 'url' in resource:
                markdown_text += f"{resource['url']}\n\n"
            else:
                markdown_text += "Web link pending\n\n"
            markdown_text += 'Contributing Projects and Cores: ' + ', '.join(contributors(resource)) + '\n\n'
    return markdown_text


def publication_events(publication):
    """Return list of (date, label) reportable events for a publication within the reporting period."""
    events = []
    preprint = publication.get('preprint') or {}
    published = publication.get('published') or {}
    if preprint.get('date') and text_date_is_in_reporting_period(preprint['date']):
        events.append((to_date(preprint['date']), f"Preprint posted to {preprint.get('server', 'preprint server')}"))
    for version in preprint.get('versions') or []:
        if int(version.get('version', 1)) > 1 and text_date_is_in_reporting_period(version['date']):
            events.append((to_date(version['date']), f"Preprint updated (v{version['version']})"))
    if published.get('date') and text_date_is_in_reporting_period(published['date']):
        events.append((to_date(published['date']), f"Published in {published.get('journal', 'journal')}"))
    return sorted(events)


def render_publication(publication, component_shortname):
    """Render a single publication citation to Markdown."""
    markdown_text = f"{publication.get('authors', '').strip()}."
    markdown_text += f" **{publication['title'].strip()}**. "

    preprint = publication.get('preprint') or {}
    published = publication.get('published') or {}
    if published:
        journal = published.get('journal', '')
        if str(published.get('pages', '')).lower() == 'in press':
            markdown_text += f"{journal} *in press*. {published.get('date', '')}."
        else:
            citation = f"{journal}"
            if published.get('volume'):
                citation += f" {published['volume']}"
            if published.get('pages'):
                citation += f":{published['pages']}"
            if published.get('year'):
                citation += f", {published['year']}"
            markdown_text += f"{citation}. Published {published.get('date', '')}. doi:{published.get('doi', '')}"
        if published.get('pmcid'):
            markdown_text += f"; PubMed Central PMCID: {published['pmcid']}"
        elif published.get('nihmsid'):
            markdown_text += f"; Submitted to PubMed Central NIHMSID: {published['nihmsid']}"
        else:
            issue(component_shortname, f'No PMCID/NIHMSID for published article "{publication["title"][:80]}" (NIH public access)')
        markdown_text += '.'
        if preprint:
            markdown_text += f" Preprint: {preprint.get('server', '')} {preprint.get('url', '')}."
    elif preprint:
        versions = preprint.get('versions') or []
        latest = versions[-1] if versions else None
        markdown_text += f"{preprint.get('server', '')} [**Preprint**]. Posted {preprint.get('date', '')}"
        if latest and int(latest.get('version', 1)) > 1:
            markdown_text += f"; latest version v{latest['version']} {latest['date']}"
        markdown_text += f". Available from: {preprint.get('url', '')}"
        if preprint.get('pmcid'):
            markdown_text += f"; PMCID: {preprint['pmcid']}"
        markdown_text += '.'
    markdown_text += '\n\n'

    events = publication_events(publication)
    if events:
        markdown_text += '*Reporting period events:* ' + '; '.join(f'{label} {date}' for date, label in events) + '\n\n'

    if publication.get('summary'):
        markdown_text += f"*{str(publication['summary']).strip()}*\n\n"
    markdown_text += 'Contributing Projects and Cores: ' + ', '.join(contributors(publication)) + '\n\n'
    return markdown_text


def render_publications(component_shortname, center_wide=False):
    """Render publications/preprints with events in the reporting period to Markdown."""
    publications = load_yaml('../data/publications/publications.yaml')
    markdown_text = ''
    reportable = []
    for publication in publications:
        if not publication_events(publication):
            continue
        if not contributors(publication):
            issue('data', f'Publication "{publication["title"][:80]}" has reporting-period events but no project/core attribution')
            continue
        if center_wide or component_contributed_to_output(component_shortname, publication):
            reportable.append(publication)
    reportable.sort(key=lambda p: publication_events(p)[0][0])
    for publication in reportable:
        markdown_text += render_publication(publication, component_shortname)
    return markdown_text


def render_outputs_section(component_shortname, component):
    """
    Render the generated outputs subsection appended to the end of section B.
    Returns (markdown_text, number_of_items_rendered)
    """
    is_admin = component_shortname == 'Administrative Core'
    period = f'{reporting_period_start.isoformat()} to {reporting_period_end.isoformat()}'
    subsections = []
    if is_admin:
        subsections.append(('Center-wide publications and preprints', render_publications(component_shortname, center_wide=True)))
    else:
        subsections.append(('Publications and preprints', render_publications(component_shortname)))
    subsections += [
        ('Research outputs', render_research_outputs(component_shortname)),
        ('Target-enabling package resources', render_TEP_outputs(component_shortname)),
        ('Software', render_software(component_shortname)),
        ('Protocols', render_protocols(component_shortname)),
        ('Datasets deposited in ChEMBL', render_chembl_datasets(component_shortname)),
        ('Patent applications', render_patents(component_shortname)),
    ]
    markdown_text = f'## Publications and research outputs during this reporting period\n\n'
    markdown_text += (f'The following publications, preprints, and research outputs from this {component["type"]} '
                      f'were posted, released, or updated during the reporting period ({period}). '
                      f'All outputs are also available online at https://asapdiscovery.org/outputs.\n\n')
    n_nonempty = 0
    for title, text in subsections:
        if text.strip():
            markdown_text += f'### {title}\n\n{text}'
            n_nonempty += 1
    if n_nonempty == 0:
        markdown_text += 'No outputs are recorded for this component during the reporting period.\n\n'
        issue(component_shortname, 'No publications or research outputs found for the reporting period')
    return markdown_text, n_nonempty


#
# Drive section documents
#

def find_drive_document(drive_dir, component_shortname):
    """Locate the Drive .docx for a component (newest by mtime if several)."""
    if not drive_dir or not os.path.isdir(drive_dir):
        return None
    candidates = [path for path in glob.glob(os.path.join(drive_dir, f'{glob.escape(component_shortname)}*.docx'))
                  if not os.path.basename(path).startswith('~$')]
    # Avoid "Project 1" matching "Project 10"
    candidates = [p for p in candidates if re.match(re.escape(component_shortname) + r'(\b|_|\.)', os.path.basename(p))]
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    if len(candidates) > 1:
        issue(component_shortname, 'Multiple Drive documents found; using newest: ' +
              ', '.join(f'"{os.path.basename(p)}"' + (' (USED)' if i == 0 else '') for i, p in enumerate(candidates)))
    return candidates[0]


def _paragraph_text(element):
    return ''.join(t.text or '' for t in element.iter(qn('w:t'))).strip()


def _count_media(elements):
    drawings = sum(len(e.findall('.//' + qn('w:drawing'))) + len(e.findall('.//' + qn('w:pict'))) for e in elements)
    tables = sum(1 for e in elements if e.tag == qn('w:tbl'))
    return drawings, tables


def analyze_drive_document(path, component_shortname):
    """
    Locate section headings in a Drive document.

    Returns dict with keys:
        'bounds': {segment: (start, end)} body-child index ranges (heading excluded) for 'pre', 'A'...'D'
        'media': {segment: (drawings, tables)}
        'comments': number of comments in the document
    """
    document = docx.Document(path)
    children = [c for c in document.element.body if c.tag != qn('w:sectPr')]
    found = {}
    for index, child in enumerate(children):
        if child.tag != qn('w:p'):
            continue
        text = _paragraph_text(child)
        for key, pattern in SECTION_PATTERNS.items():
            if key not in found and pattern.match(text):
                # enforce order: a later section heading must come after earlier ones found
                if all(found[k] < index for k in found if k < key):
                    found[key] = index
                break

    for key in 'BCD':
        if key not in found:
            issue(component_shortname, f'Drive document is missing a "{SECTION_TITLES[key]}" heading', 'error')
    order = sorted(found.items(), key=lambda kv: kv[1])
    if [k for k, _ in order] != sorted(found):
        issue(component_shortname, 'Drive document section headings are out of order: ' + ', '.join(k for k, _ in order), 'error')

    bounds = {}
    starts = [(k, i) for k, i in order]
    bounds['pre'] = (0, starts[0][1] if starts else len(children))
    for n, (key, index) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else len(children)
        bounds[key] = (index + 1, end)

    # Truncate the last section at any trailing (previously generated) compliance/publication sections
    if starts:
        last_key, last_index = starts[-1]
        end_markers = [i for i in range(last_index + 1, len(children))
                       if children[i].tag == qn('w:p') and END_OF_PLANS_PATTERN.match(_paragraph_text(children[i]))]
        if end_markers:
            bounds[last_key] = (bounds[last_key][0], end_markers[0])
            dropped = sorted({_paragraph_text(children[i]) for i in end_markers if not RESOURCES_PATTERN.match(_paragraph_text(children[i]))})
            if dropped:
                issue(component_shortname, f'Drive document contains sections after {SECTION_TITLES[last_key]} that are regenerated by the script and were dropped: ' + ', '.join(f'"{d}"' for d in dropped))
        resources = [i for i in end_markers if RESOURCES_PATTERN.match(_paragraph_text(children[i]))]
        if resources:
            start = resources[0] + 1
            following = [i for i in end_markers if i > resources[0]]
            bounds['R'] = (start, following[0] if following else len(children))
            issue(component_shortname, 'Using author-provided "Project Generated Resources" text from the Drive document', 'info')
    media = {k: _count_media(children[s:e]) for k, (s, e) in bounds.items()}

    for key, index in found.items():
        heading_text = _paragraph_text(children[index])
        if heading_text != SECTION_TITLES[key]:
            issue(component_shortname, f'Heading "{heading_text}" normalized to "{SECTION_TITLES[key]}"', 'info')

    n_comments = 0
    for rel in document.part.rels.values():
        if rel.reltype.endswith('/comments'):
            n_comments = len(rel.target_part.element.findall(qn('w:comment'))) if hasattr(rel.target_part, 'element') \
                else rel.target_part.blob.count(b'<w:comment ')
    if n_comments:
        issue(component_shortname, f'{n_comments} unresolved comment(s) in Drive document "{os.path.basename(path)}" (comments are not carried into the output)')

    return {'bounds': bounds, 'media': media, 'comments': n_comments}


def drive_segment_document(path, bounds, segment, component_shortname):
    """
    Load the Drive document and strip it down to the body elements of one segment, removing
    template instruction text, comment anchors, and leading/trailing empty paragraphs.
    """
    document = docx.Document(path)
    body = document.element.body
    children = [c for c in body if c.tag != qn('w:sectPr')]
    start, end = bounds[segment]
    keep = children[start:end]
    for child in children:
        if not any(child is k for k in keep):
            body.remove(child)

    # Template instruction text left by authors (e.g. "Describe the studies directed toward...") is kept as written.

    # Strip comment anchors (comments part is not carried over)
    for tag in ('w:commentRangeStart', 'w:commentRangeEnd'):
        for element in body.findall('.//' + qn(tag)):
            element.getparent().remove(element)
    for reference in body.findall('.//' + qn('w:commentReference')):
        run = reference.getparent()
        run.getparent().remove(run)

    # Trim empty paragraphs at both ends
    def is_empty(element):
        return (element.tag == qn('w:p') and not _paragraph_text(element)
                and not element.findall('.//' + qn('w:drawing')) and not element.findall('.//' + qn('w:pict')))
    # Drop empty heading-styled paragraphs (they pollute the navigation pane / table of contents)
    for child in list(keep):
        if is_empty(child):
            style = child.find(qn('w:pPr') + '/' + qn('w:pStyle'))
            has_break = any(b.get(qn('w:type')) == 'page' for b in child.iter(qn('w:br')))
            if style is not None and style.get(qn('w:val'), '').lower().startswith('heading') and not has_break:
                body.remove(child)
                keep.remove(child)
    while keep and is_empty(keep[0]):
        body.remove(keep.pop(0))
    while keep and is_empty(keep[-1]):
        body.remove(keep.pop())
    return document, len(keep)


#
# Report assembly
#

def build_front(component_shortname, component, drive_info):
    """Header, title, component-type-specific narrative, and A. Specific Aims (unless provided by Drive)."""
    document = docx.Document(DOCX_TEMPLATE)
    document.sections[0].header.paragraphs[0].add_run('Chodera, John Damon').bold = True
    document.add_heading(component['name'], 0)

    markdown_text = ''
    if component_shortname == 'Administrative Core':
        pass  # Overall narrative comes from the Drive document ('pre' segment)
    elif component['type'] == 'Project':
        markdown_text += "# Significant changes in the Specific Aims\n\n"
        if component['funded_aims_modified']:
            markdown_text += 'The Specific Aims have been modified from the original, competing application as described in "A. Specific Aims" below.\n\n'
        else:
            markdown_text += 'The Specific Aims have not been modified from the original, competing application.\n\n'
        markdown_text += '# Significance of the work\n\n'
        markdown_text += component['significance'] + '\n\n'
        markdown_text += '# Product development milestones\n\n'
        if 'product_development_milestones' in component:
            markdown_text += component['product_development_milestones'] + '\n\n'
        else:
            markdown_text += 'This component does not have any product development milestones because it only supports the discovery stage.\n\n'
        markdown_text += "# Significant Project-Generated Resources\n\n"
        markdown_text += 'Publications, preprints, and research outputs generated by this Project during the reporting period are listed at the end of "B. Studies and Results".\n\n'
    elif component['type'] == 'Core':
        markdown_text += "# Individual Research Projects served and activities performed and/or completed\n\n"
        if 'projects_served' in component:
            markdown_text += component['projects_served'] + '\n\n'
        markdown_text += "# Significant Core-Generated Resources\n\n"
        markdown_text += 'Publications, preprints, and research outputs generated by this Core during the reporting period are listed at the end of "B. Studies and Results".\n\n'
    render_markdown(document, markdown_text)
    return document


OVERALL_ACCOMPLISHMENTS = 'Overall Accomplishments'
OVERALL_ACCOMPLISHMENTS_TEXT = ('The overall review of accomplishments is included in the Administrative Core '
                                'per NIAID PO direction.')


def generate_overall_accomplishments(output_path):
    """Center-level "Overall Accomplishments" document pointing to the Administrative Core report."""
    document = docx.Document(DOCX_TEMPLATE)
    document.sections[0].header.paragraphs[0].add_run('Chodera, John Damon').bold = True
    document.add_heading(OVERALL_ACCOMPLISHMENTS, 0)
    document.add_paragraph(OVERALL_ACCOMPLISHMENTS_TEXT)
    output_filename = os.path.join(output_path, f'{OVERALL_ACCOMPLISHMENTS}.docx')
    document.save(output_filename)
    print(f'Wrote {output_filename}')
    return output_filename


def find_soffice():
    for candidate in (shutil.which('soffice'), shutil.which('libreoffice'),
                      '/Applications/LibreOffice.app/Contents/MacOS/soffice'):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def convert_to_pdf(docx_paths, output_path):
    """
    Render each generated .docx to a .pdf alongside it. Uses LibreOffice (soffice) if installed, otherwise
    Microsoft Word via docx2pdf (macOS/Windows; Word may ask once for permission to access the folder).
    """
    import subprocess
    if not docx_paths:
        return
    soffice = find_soffice()
    print(f'Rendering {len(docx_paths)} PDF(s) using {"LibreOffice" if soffice else "Microsoft Word (docx2pdf)"}')
    for path in docx_paths:
        pdf_path = os.path.splitext(path)[0] + '.pdf'
        try:
            if soffice:
                subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', output_path, path],
                               check=True, capture_output=True, timeout=600)
            else:
                from docx2pdf import convert
                convert(path, pdf_path)
        except ImportError:
            issue('pdf', 'No PDF converter available: install LibreOffice or `pip install docx2pdf` (requires Microsoft Word)', 'error')
            return
        except Exception as e:
            issue('pdf', f'PDF conversion failed for {os.path.basename(path)}: {type(e).__name__}: {e}', 'error')
            continue
        if not os.path.exists(pdf_path):
            if soffice:
                issue('pdf', f'PDF conversion produced no output for {os.path.basename(path)}', 'error')
                continue
            # docx2pdf swallows Word automation errors; the usual cause on macOS is a missing Automation
            # permission (AppleEvent error -1743), which would fail every remaining file the same way.
            issue('pdf', f'Microsoft Word produced no PDF for {os.path.basename(path)}. On macOS, allow your terminal '
                         'to control Microsoft Word (System Settings > Privacy & Security > Automation), then re-run; '
                         'or install LibreOffice. Remaining PDFs skipped.', 'error')
            return
        else:
            print(f'  Wrote {pdf_path}')


def build_heading(title, page_break=True, markdown_text=''):
    document = new_document()
    if page_break:
        document.add_page_break()
    document.add_heading(title, 1)
    render_markdown(document, markdown_text)
    return document


def build_specific_aims(component, page_break=True):
    if component['funded_aims_modified']:
        text = component['aims'] + '\n\n'
    else:
        text = 'The Specific Aims have not been modified from the original, competing application.\n\n'
    return build_heading(SECTION_TITLES['A'], page_break, text)


def build_structural_biology_statistics():
    spreadsheets = {
        'SARS-CoV-2 Mpro protease': 'SARS_Mpro_SBC_Analysis.xlsx',
        'MERS-CoV Mpro protease': 'MERS_Mpro_SBC_Analysis.xlsx',
        'SARS-CoV-2 nsp3 Mac1 macrodomain': 'Nsp3_Mac1_SBC_Analysis.xlsx',
    }
    markdown_text = ''
    for target, filename in spreadsheets.items():
        path = os.path.join('structural-biology-core-data', filename)
        if not os.path.exists(path):
            issue('Structural Biology Core', f'Experiment statistics spreadsheet {path} not found; statistics omitted', 'info')
            continue
        import pandas as pd
        sheet = pd.read_excel(path, sheet_name='Experiment_Summary')
        markdown_text += f'For **{target}**, the following experiments have been conducted during the reporting period:\n\n'
        counts = sheet['Experiment Status'].value_counts().to_dict()
        for name, count in counts.items():
            markdown_text += f'* {count} : {name}\n'
        markdown_text += '\n'
    return markdown_text


CDD_ASSAY_DATA = os.path.join('cdd-data', 'cdd-assay-measurements.csv')
CDD_ASSAY_COMPONENTS = ('Biochemical Assay Core',)  # components whose reports include the CDD assay statistics


def load_program_names():
    """Map ASAP program codes to program names: data/programs/*.yaml, with data/outputs/TEPs/*.yaml as fallback."""
    import glob
    names = {}
    for path in sorted(glob.glob('../data/outputs/TEPs/*.yaml')):
        tep = (load_yaml(path) or {}).get('TEP') or {}
        code = (tep.get('asap') or {}).get('program_code')
        if code and tep.get('name'):
            names.setdefault(code, tep['name'])
    for path in sorted(glob.glob('../data/programs/*.yaml')):
        overview = (load_yaml(path) or {}).get('overview') or {}
        if overview.get('program_code') and overview.get('name'):
            names[overview['program_code']] = overview['name']
    if os.path.exists('cdd-program-codes.yaml'):
        names.update(load_yaml('cdd-program-codes.yaml') or {})
    return names


def build_assay_statistics(component_shortname):
    """
    Summarize compound measurements run at contract research sites (Bienta/Enamine, Weizmann) during the
    reporting period, from the CDD Vault export written by fetch-cdd-assays.py.
    """
    if not os.path.exists(CDD_ASSAY_DATA):
        issue(component_shortname, f'CDD assay data {CDD_ASSAY_DATA} not found; run fetch-cdd-assays.py', 'info')
        return ''
    import pandas as pd
    data = pd.read_csv(CDD_ASSAY_DATA, dtype=str, keep_default_na=False)
    dates = pd.to_datetime(data['run_date']).dt.date
    data = data[(dates >= reporting_period_start) & (dates <= reporting_period_end)]
    if data.empty:
        issue(component_shortname, 'CDD assay data has no measurements in the reporting period', 'warning')
        return ''

    program_names = load_program_names()

    def program_label(code):
        if not code:
            return 'no program assigned'
        if code not in program_names:
            issue('data', f'CDD program_code {code} has no program name in data/programs or data/outputs/TEPs')
            return code
        return f'{program_names[code]} ({code})'

    for code in sorted(set(data.loc[data['program_code'] == '', 'protocol'])):
        issue('data', f'CDD protocol {code} has measurements with no program_code batch field')
    for protocol, description in data.groupby('protocol')['protocol_description'].first().items():
        if not description.strip():
            issue('data', f'CDD protocol {protocol} has no description')

    markdown_text = '## Assays performed at contract research sites during this reporting period\n\n'
    markdown_text += ('Counts are compound measurements (one compound tested in one assay run; dose-response points and '
                      'replicates within a run are counted once), compiled from the ASAP Discovery CDD Vault for runs dated '
                      f'{reporting_period_start.isoformat()} to {reporting_period_end.isoformat()}.\n\n')
    for site, site_data in data.groupby('site', sort=True):
        markdown_text += (f'**{site}** performed {len(site_data):,} compound measurements of '
                          f'{site_data["cdd_number"].nunique():,} unique compounds in {site_data["run_id"].nunique():,} runs '
                          f'across {site_data["protocol"].nunique()} assay protocols:\n\n')
        protocols = site_data.groupby('protocol')
        for protocol in sorted(protocols.groups, key=lambda p: -len(protocols.get_group(p))):
            rows = protocols.get_group(protocol)
            description = rows['protocol_description'].iloc[0].strip()
            per_program = rows['program_code'].value_counts()
            breakdown = '; '.join(f'{program_label(code)}: {count:,}' for code, count in per_program.items())
            markdown_text += (f'* **{protocol}**' + (f' ({description})' if description else '')
                              + f': {len(rows):,} measurements of {rows["cdd_number"].nunique():,} compounds in '
                              f'{rows["run_id"].nunique()} runs. By program: {breakdown}.\n')
        markdown_text += '\n'
    return markdown_text


def build_trailer(component_shortname, component):
    markdown_text = '---\n\n'
    for title in ('Human Subjects', 'Inclusion of Women and Minorities in Clinical Research',
                  'Human Subjects Education Requirement'):
        markdown_text += f'# {title}\n\nNot applicable\n\n'
    markdown_text += '# Vertebrate Animals\n\n'
    markdown_text += ('No change\n\n' if component.get('uses_vertebrate_animals', False) else 'Not applicable\n\n')
    for title in ('Select Agent Research', 'Human Embryonic Stem Cell Line(s) Used'):
        markdown_text += f'# {title}\n\nNot applicable\n\n'
    if component['type'] == 'Project' or component_shortname == 'Administrative Core':
        markdown_text += '# Project Generated Resources\n\n'
        markdown_text += 'See the list of publications, preprints, and research outputs at the end of "B. Studies and Results".\n\n'
    document = new_document()
    render_markdown(document, markdown_text)
    return document


def generate_progress_report(component_shortname, component, output_path, drive_dir, legacy):
    """
    Generate a progress report for the specified Project or Core.

    Returns a dict summarizing what was assembled (for post-generation checks).
    """
    from docxcompose.composer import Composer

    summary = {'component': component_shortname, 'drive_document': None, 'expected_media': (0, 0)}

    drive_path = find_drive_document(drive_dir, component_shortname)
    drive_info = None
    if drive_path:
        summary['drive_document'] = os.path.basename(drive_path)
        print(f'  Using Drive document: {os.path.basename(drive_path)}')
        drive_info = analyze_drive_document(drive_path, component_shortname)
    else:
        issue(component_shortname, f'No Drive document found in {drive_dir}; falling back to legacy YAML text for B/C/D', 'error')

    bounds = drive_info['bounds'] if drive_info else {}
    composer = Composer(build_front(component_shortname, component, drive_info))
    expected_drawings, expected_tables = 0, 0

    def append_drive_segment(segment):
        nonlocal expected_drawings, expected_tables
        segment_document, n_elements = drive_segment_document(drive_path, bounds, segment, component_shortname)
        drawings, tables = _count_media([c for c in segment_document.element.body if c.tag != qn('w:sectPr')])
        expected_drawings += drawings
        expected_tables += tables
        if n_elements == 0:
            issue(component_shortname, f'Drive section {SECTION_TITLES.get(segment, segment)} is empty', 'error')
        composer.append(segment_document)

    # Overall narrative before section A (Administrative Core only)
    if drive_info and bounds['pre'][1] > bounds['pre'][0]:
        pre_document, n_pre = drive_segment_document(drive_path, bounds, 'pre', component_shortname)
        if n_pre:
            if component_shortname == 'Administrative Core':
                append_drive_segment('pre')
            else:
                issue(component_shortname, f'Drive document has {n_pre} non-empty element(s) before the first section heading; omitted')

    # A. Specific Aims
    if drive_info and 'A' in bounds:
        composer.append(build_heading(SECTION_TITLES['A']))
        append_drive_segment('A')
    else:
        composer.append(build_specific_aims(component))

    # B. Studies and Results
    composer.append(build_heading(SECTION_TITLES['B']))
    if drive_info and 'B' in bounds:
        append_drive_segment('B')
    else:
        text = ''
        if component_shortname in legacy['accomplishments']:
            text = 'Significant accomplishments include:\n\n' + legacy['accomplishments'][component_shortname] + '\n\n'
        issue(component_shortname, 'B. Studies and Results uses legacy text from asap-year-1-accomplishments.yaml', 'error')
        composer.append(render_markdown(new_document(), text))
    if component_shortname == 'Structural Biology Core':
        stats = build_structural_biology_statistics()
        if stats:
            document = new_document()
            render_markdown(document, stats)
            composer.append(document)
    if component_shortname in CDD_ASSAY_COMPONENTS:
        stats = build_assay_statistics(component_shortname)
        if stats:
            document = new_document()
            render_markdown(document, stats)
            composer.append(document)

    # Generated outputs at the end of section B
    outputs_markdown, n_subsections = render_outputs_section(component_shortname, component)
    outputs_document = new_document()
    render_markdown(outputs_document, outputs_markdown)
    composer.append(outputs_document)
    summary['output_subsections'] = n_subsections

    # C. Significance
    if drive_info and 'C' in bounds:
        composer.append(build_heading(SECTION_TITLES['C']))
        append_drive_segment('C')
    else:
        composer.append(build_heading(SECTION_TITLES['C'], markdown_text=component['significance'] + '\n\n'))
        issue(component_shortname, 'C. Significance uses generic text from specific-aims.yaml', 'error')

    # D. Plans
    if drive_info and 'D' in bounds:
        composer.append(build_heading(SECTION_TITLES['D']))
        append_drive_segment('D')
    else:
        text = ''
        if component_shortname in legacy['plans']:
            text = 'Plans for the next project period include:\n\n' + legacy['plans'][component_shortname] + '\n\n'
        composer.append(build_heading(SECTION_TITLES['D'], markdown_text=text))
        issue(component_shortname, 'D. Plans uses legacy text from asap-year-1-plans.yaml', 'error')

    # Compliance sections
    composer.append(build_trailer(component_shortname, component))
    if drive_info and 'R' in bounds:
        append_drive_segment('R')

    output_filename = os.path.join(output_path, component_shortname + '.docx')
    lock_filename = os.path.join(output_path, '~$' + (component_shortname + '.docx')[2:])
    if os.path.exists(lock_filename):
        issue(component_shortname, f'{output_filename} appears to be open in Word ({os.path.basename(lock_filename)}); close it and re-run if saving fails')
    composer.save(output_filename)

    if os.path.exists('tmp'):
        shutil.rmtree('tmp')

    summary['output'] = output_filename
    summary['expected_media'] = (expected_drawings, expected_tables)
    return summary


#
# Post-generation checks
#

def check_report(summary):
    component_shortname = summary['component']
    document = docx.Document(summary['output'])
    children = [c for c in document.element.body if c.tag != qn('w:sectPr')]
    texts = [_paragraph_text(c) for c in children if c.tag == qn('w:p')]

    positions = {}
    for key, title in SECTION_TITLES.items():
        count = texts.count(title)
        if count != 1:
            issue(component_shortname, f'Output contains "{title}" {count} times (expected 1)', 'error')
        if count:
            positions[key] = texts.index(title)
    if [k for k, _ in sorted(positions.items(), key=lambda kv: kv[1])] != sorted(positions):
        issue(component_shortname, 'Output section order is not A, B, C, D', 'error')

    drawings, tables = _count_media(children)
    expected_drawings, expected_tables = summary['expected_media']
    if drawings < expected_drawings:
        issue(component_shortname, f'Output has {drawings} figures but Drive sections had {expected_drawings}; figures may have been lost', 'error')
    if tables < expected_tables:
        issue(component_shortname, f'Output has {tables} tables but Drive sections had {expected_tables}; tables may have been lost', 'error')
    summary['media'] = (drawings, tables)

    # Placeholder / reminder text authors may have left in
    for text in texts:
        if re.search(r'\b(TODO|TBD|XXX|\?\?\?)\b|\[(insert|add|cite)[^\]]*\]', text, re.I):
            issue(component_shortname, f'Possible placeholder text: "{text[:100]}"')


def write_issues_report(path, summaries):
    severity_rank = {'error': 0, 'warning': 1, 'info': 2}
    lines = [f'# RPPR generation issues ({datetime.date.today()})', '',
             f'Reporting period: {reporting_period_start} to {reporting_period_end}', '',
             '## Generated reports', '',
             '| Component | Drive document | Output subsections | Figures / tables (output) | Figures / tables (Drive) |',
             '|---|---|---|---|---|']
    for s in summaries:
        lines.append(f"| {s['component']} | {s.get('drive_document') or '**none**'} | {s.get('output_subsections', '')} | "
                     f"{'%d / %d' % s['media'] if 'media' in s else ''} | {'%d / %d' % s['expected_media']} |")
    lines += ['']
    components = [s['component'] for s in summaries] + ['data']
    for component in components:
        items = sorted([i for i in ISSUES if i[0] == component], key=lambda i: severity_rank[i[1]])
        if not items:
            continue
        lines += [f'## {component}', '']
        lines += [f'- **{severity}**: {message}' for _, severity, message in items]
        lines += ['']
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {path}')


def main():
    global reporting_period_start, reporting_period_end

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--drive-sections', default=DEFAULT_DRIVE_SECTIONS,
                        help='Folder containing "<Component>*.docx" files with B/C/D sections')
    parser.add_argument('--output-dir', default='outputs')
    parser.add_argument('--components', nargs='+', help='Only generate these components (default: all)')
    parser.add_argument('--period-start', default=reporting_period_start.isoformat())
    parser.add_argument('--period-end', default=reporting_period_end.isoformat())
    parser.add_argument('--no-pdf', action='store_true', help='Skip rendering PDF versions of the generated .docx files')
    args = parser.parse_args()

    output_path = os.path.abspath(args.output_dir)
    os.chdir(HERE)  # all data paths are relative to this script
    reporting_period_start = datetime.date.fromisoformat(args.period_start)
    reporting_period_end = datetime.date.fromisoformat(args.period_end)
    print(f'Reporting period: {reporting_period_start} to {reporting_period_end}')
    if not os.path.isdir(args.drive_sections):
        print(f'WARNING: Drive sections folder not found: {args.drive_sections}')

    components = load_yaml('specific-aims.yaml')
    legacy = {
        'accomplishments': load_yaml('asap-year-1-accomplishments.yaml') or {},
        'plans': load_yaml('asap-year-1-plans.yaml') or {},
    }

    # Check data attribution names
    for path in glob.glob('../data/**/*.yaml', recursive=True):
        def walk(node):
            if isinstance(node, dict):
                for key in ('projects', 'cores'):
                    for name in node.get(key) or [] if isinstance(node.get(key), list) else []:
                        if normalize_component(name) not in components:
                            issue('data', f'Attribution "{name}" (in {os.path.relpath(path, "../data")}) is not a component in specific-aims.yaml; those outputs are not reported for it')
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(load_yaml(path))

    os.makedirs(output_path, exist_ok=True)
    summaries = []
    for component_shortname, component in components.items():
        if args.components and component_shortname not in args.components:
            continue
        if component.get('discontinued', False):
            print(f'Skipping discontinued component {component_shortname}')
            continue
        print(f"Generating report for {component['name']} ({component_shortname})")
        summary = generate_progress_report(component_shortname, component, output_path, args.drive_sections, legacy)
        check_report(summary)
        summaries.append(summary)

    generated = [s['output'] for s in summaries if s.get('output')]
    if not args.components or OVERALL_ACCOMPLISHMENTS in args.components:
        generated.append(generate_overall_accomplishments(output_path))
    if not args.no_pdf:
        convert_to_pdf(generated, output_path)

    write_issues_report(os.path.join(output_path, 'rppr-issues.md'), summaries)


if __name__ == "__main__":
    main()

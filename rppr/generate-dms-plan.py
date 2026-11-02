#!/usr/bin/env python
"""
Fill the NIH 2026 Data Management and Sharing (DMS) Plan format page (dms-blank-format-page-2026.docx) for ASAP.

Usage (from rppr/):
    python generate-dms-plan.py [--no-pdf]

Writes outputs/Data Management and Sharing Plan.docx (and a flattened PDF via generate-rppr.py's converter).
Plan text is drawn from the Administrative Core data-dissemination narrative and the 2024 ASAP data-sharing
supplement Research Strategy; edit the ANSWERS/LIMITATIONS/DATA_TYPES below to revise it.

Guidance: https://grants.nih.gov/policy-and-compliance/policy-topics/sharing-policies/dms/writing-dms-plan
"""

import argparse
import copy
import importlib.util
import os
import re

import docx
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.table import _Cell
from docx.text.paragraph import Paragraph

TEMPLATE = 'dms-blank-format-page-2026.docx'
OUTPUT = os.path.join('outputs', 'Data Management and Sharing Plan.docx')
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'

# Checkbox answers, in template order: elements 1, 2, 3, 5, 7a, 7b
ANSWERS = ['Yes', 'Yes', 'Yes', 'Not Applicable', 'Not Applicable', 'Not Applicable']

# Element 4 (300 words maximum)
LIMITATIONS = [
    'ASAP shares all scientific data openly. Two time-limited exceptions are set by the ASAP IP and Open Science '
    'Policy (Griffen and Boulet, Wellcome Open Research 2024; https://asapdiscovery.org/open-science/), which uses '
    'minimal defensive patenting so that ASAP antivirals can be licensed non-exclusively and royalty-free for '
    'global, equitable, and affordable access.',

    '(1) Compounds selected for development. When a lead optimization program (Projects 3 and 5) selects compounds '
    'to develop (typically one, at most three), a single-compound composition-of-matter patent application is filed '
    'with the earliest possible publication date. Chemical structures and assay data for these compounds, and for '
    'analogs not sufficiently differentiated from them, are withheld until the application publishes. All other '
    'compounds are disclosed on a rolling basis through quarterly disclosure reviews.',

    '(2) Preclinical development data. In vivo pharmacokinetic, safety, and toxicology data for development '
    'candidates (Project 6) are released once the IND-equivalent data package is complete.',

    'Data underlying publications and preprints are always shared no later than publication. If either restriction '
    'lapses after the end of the period of performance, the affected data will be shared as soon as it lapses. No '
    'human participant data are generated.',
]

# Element 6 table (100 words maximum): (expected data type, established repository or example)
DATA_TYPES = [
    ('Small-molecule structures with biochemical, antiviral, and ADMET assay data', 'ChEMBL'),
    ('X-ray crystal structures of viral protein targets, including fragment screens',
     'Protein Data Bank'),
    ('Viral deep mutational scanning sequencing data', 'Zenodo'),
    ('Assay, protein expression, and purification protocols', 'protocols.io'),
    ('Expression plasmid sequences', 'Addgene'),
    ('Rodent and dog pharmacokinetic and efficacy data', 'Zenodo'),
    ('Target enabling packages, product/candidate profiles, assay cascades', 'Zenodo'),
    ('Software and computational models', 'GitHub, archived in Zenodo'),
]

ELEMENT_6_LEAD = 'Key types of scientific data and repositories:'


def words(text):
    return len(re.findall(r'\S+', text))


def is_italic(run):
    rpr = run._r.rPr
    if run.italic:
        return True
    return run.italic is None and rpr is not None and rpr.find(qn('w:i')) is not None


def delete(paragraph):
    paragraph._p.getparent().remove(paragraph._p)


def set_checkbox(sdt, checked):
    box = sdt.find('.//{%s}checkbox' % W14)
    box.find('{%s}checked' % W14).set('{%s}val' % W14, '1' if checked else '0')
    state = box.find('{%s}%s' % (W14, 'checkedState' if checked else 'uncheckedState'))
    sdt.find('.//' + qn('w:sdtContent')).find('.//' + qn('w:t')).text = chr(int(state.get('{%s}val' % W14), 16))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--no-pdf', action='store_true')
    args = parser.parse_args()

    limitation_words = sum(words(p) for p in LIMITATIONS)
    table_words = sum(words(a) + words(b) for a, b in DATA_TYPES)
    assert limitation_words <= 300, f'Element 4 has {limitation_words} words (300 maximum)'
    assert table_words <= 100, f'Element 6 table has {table_words} words (100 maximum)'

    document = docx.Document(TEMPLATE)
    paragraphs = document.paragraphs

    # Yes/No/Not Applicable checkboxes
    choice_paragraphs = [p for p in paragraphs if p.text.strip().startswith('Yes No')]
    assert len(choice_paragraphs) == len(ANSWERS)
    for paragraph, answer in zip(choice_paragraphs, ANSWERS):
        options = ['Yes', 'No', 'Not Applicable'][:len(paragraph._p.findall(qn('w:sdt')))]
        assert answer in options, (answer, options)
        for sdt, option in zip(paragraph._p.findall(qn('w:sdt')), options):
            set_checkbox(sdt, option == answer)

    # Element 4: drop the italic word limit and write the limitations into the blank paragraph that follows
    element_4 = next(p for p in paragraphs if p.text.startswith('If you answered'))
    answer_slot = paragraphs[paragraphs.index(element_4) + 1]
    assert not answer_slot.text.strip()
    for _ in LIMITATIONS[1:]:
        answer_slot._p.addnext(copy.deepcopy(answer_slot._p))
    node = answer_slot._p
    for paragraph_text in LIMITATIONS:
        paragraph = Paragraph(node, answer_slot._parent)
        paragraph.add_run(paragraph_text)
        paragraph.paragraph_format.space_after = Pt(6)
        node = node.getnext()

    # Element 6: plain lead-in, then the table
    element_6 = next(p for p in paragraphs if p.text.startswith('In the table below'))
    for run in element_6.runs[1:]:
        run._r.getparent().remove(run._r)
    element_6.runs[0].text = ELEMENT_6_LEAD
    element_6.runs[0].italic = False
    table = document.tables[0]
    blank_row = table.rows[1]._tr
    table._tbl.remove(blank_row)
    for data_type, repository in DATA_TYPES:
        row = copy.deepcopy(blank_row)
        table._tbl.append(row)
        cells = row.findall(qn('w:tc'))
        for cell, text in zip(cells, (data_type, repository)):
            _Cell(cell, table).paragraphs[0].add_run(text)

    # Delete italic instructions (per the template: "you should delete the text in italics")
    for paragraph in list(document.paragraphs):
        if paragraph.style.name == 'Heading Note':
            delete(paragraph)
            continue
        italic = [r for r in paragraph.runs if is_italic(r)]
        if italic and len(italic) == len([r for r in paragraph.runs if r.text.strip()]):
            delete(paragraph)  # wholly italic instruction paragraph
        else:
            for run in italic:
                run._r.getparent().remove(run._r)
    # Drop the blank spacer paragraphs left behind the deleted element 6 instructions
    element_6 = next(p for p in document.paragraphs if p.text == ELEMENT_6_LEAD)
    nxt = element_6._p.getnext()
    while nxt is not None and nxt.tag == qn('w:p') and not ''.join(nxt.itertext()).strip():
        following = nxt.getnext()
        nxt.getparent().remove(nxt)
        nxt = following

    os.makedirs('outputs', exist_ok=True)
    document.save(OUTPUT)
    print(f'Wrote {OUTPUT} (element 4: {limitation_words}/300 words; element 6 table: {table_words}/100 words)')

    if not args.no_pdf:
        spec = importlib.util.spec_from_file_location('generate_rppr', 'generate-rppr.py')
        generate_rppr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generate_rppr)
        generate_rppr.convert_to_pdf([os.path.abspath(OUTPUT)], os.path.abspath('outputs'))


if __name__ == '__main__':
    main()

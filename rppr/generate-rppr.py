"""
Generate the RPPR report for ASAP AViDD U19 year 1.

TODO:
* Switch to using markdown2docx in future, which enables better control over mappings from Markdown styles to Word Styles?
  https://pypi.org/project/Markdown2docx/

"""

# -*- coding: utf-8 -*-

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm

#
# Define Markdown to docx renderer
#

import mistune

class MathBlockGrammar(mistune.BlockGrammar):
    import re
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

# Generate the code to render the document
# TODO: Convert this to actually execute the code on a provided document object instead of jut returning it
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
        add_break = '' if text.endswith(':")\n') else 'p.add_run().add_break()'
        add_break = '' # DEBUG
        return '\n'.join(('p = document.add_paragraph()', text, add_break)) + '\n'

    def list(self, body, ordered):
        #return body + '\np.add_run().add_break()\n'
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
        import re
        text = re.sub("\s+", " ", text)
        text = re.sub('"', '\\"', text)        
        return "p.add_run(\"%s\")\n" % text

    def emphasis(self, text):
        return text[:-1] + '.italic = True\n'

    def double_emphasis(self, text):
        return text[:-1] + '.bold = True\n'

    def codespan(self, text):
        return "p.add_run(\"%s\", style=\"CodeSpan\")\n" % text

    def block_code(self, code, language):
        code = code.replace('\n', '\\n')
        return "p = document.add_paragraph()\np.add_run(\"%s\")\np.style = 'BlockCode'\np.add_run().add_break()\n" % code

    def link(self, link, title, content):
        return f'p.add_run("{content} [")\np.add_run("{link}", style="CodeSpan")\np.add_run("]")\n'

    def autolink(self, link, is_email=False):
        # TODO: Render autolinks
        return f'p.add_run("{link}", style="CodeSpan")\n'

    def inline_html(self, text):
        # DEBUG
        return ""

    def image(self, src, title, alt_text):
        return '\n'.join((
            "p = document.add_paragraph()",
            "p.alignment = WD_ALIGN_PARAGRAPH.CENTER",
            "p.space_after = Pt(18)",
            "run = p.add_run()",
            "run.add_picture(\'%s\')" % src if "tmp" in src else "run.add_picture(\'%s\', width=Cm(15))" % src,
            "run.add_break()",
            "run.add_text(\'%s\')" % alt_text,
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

def get_components(yaml_filename='specific-aims.yaml'):
    """
    Retrieve all component short and full names

    Returns
    -------
    components : dict of str : str
        components[short_name] is the long name of that component
    """
    # Read Specific Aims from YAML file 'specific-aims.yaml'
    import yaml
    with open(yaml_filename, 'r') as f:
        components = yaml.load(f, Loader=yaml.SafeLoader)

    return components    

def get_specific_aims(component_name):
    """
    Retrieve the text for the Specific Aims section of the Progress Report for the specified Project or Core

    -----------
    component_name: str
        Name of the project or core to generate a report for.
    """
    # Read Specific Aims from YAML file 'specific-aims.yaml'
    import yaml
    specific_aims_filename = 'specific-aims.yaml'
    with open(specific_aims_filename, 'r') as f:
        specific_aims = yaml.load(f, Loader=yaml.SafeLoader)
    # Check to make sure the Specific Aims can be found for this Project or Core
    if not component_name in specific_aims:
        raise ValueError(f'No Specific Aims found for component {component_name} in {specific_aims_filename}')

    if specific_aims[component_name]['funded_aims_modified']:
        return specific_aims[component_name]['aims']
    else:
        return "The Aims of this component have not been modified from the original, competing application."

def get_publications():
    """
    Retrieve all publications

    Returns
    -------
    publications : list of dict
        publication[index] is the dict with info on a publication

    """
    import yaml
    publications_filename = '../data/publications/publications.yaml'
    with open(publications_filename, 'r') as f:
        publications = yaml.load(f, Loader=yaml.SafeLoader)
    return publications

def generate_progress_report(component_shortname, component, output_path):
    """
    Generate a project report for the specified Project or Core

    Parameters:
    -----------
    component_shortname : str
        Component short name key used in data tables
    component : dict
        Component metadata containing fields
            name: full neame
            type: Project or Core
            significance: the significance of this Project or Core
            funded_aims_modified: if Specific Aims have been modified from submitted proposal
            aims: Specific Aims
    output_path : str
        Name of output path to write report to.

    """
    accomplishments = get_components(yaml_filename='asap-year-1-accomplishments.yaml')
    plans = get_components(yaml_filename='asap-year-1-plans.yaml')

    # Use docx to generate Word documents on continuation pages directly.
    # See https://python-docx.readthedocs.io/
    import docx

    # Load the template and extract styles
    docx_template_filename = "2590_continuation-template.docx"
    document = docx.Document(docx_template_filename)
    #styles = document.styles
    #from docx.enum.style import WD_STYLE_TYPE
    #paragraph_styles = [
    #    s for s in styles if s.type == WD_STYLE_TYPE.PARAGRAPH
    #]
    #for style in paragraph_styles:
    #    print(style.name)

    # Configure the header
    document.sections[0].header.paragraphs[0].add_run('Chodera, John Damon').bold = True

    # Construct markdown text for content of the report
    markdown_text = ""

    # Add heading for Project/Core name
    document.add_heading(component['name'], 0)

    # Add requested narrative information to go before the standard Progress Report material
    if component_shortname == 'Administrative Core':
        #
        # Administrative core
        #
        
        # A manually-asembled narrative goes in front
        pass        

    elif component['type'] == 'Project':
        #
        # Project-specific narrative
        #

        # Significant changes in the Specific Aims
        # TODO: Should this section describe any changes in approach during the past year?
        markdown_text += "# Significant changes in the Specific Aims\n\n"
        if component['funded_aims_modified']:
            markdown_text += 'The Specific Aims have been modified from the original, competing application as described in "A. Specific Aims" below.\n\n'
        else:
            markdown_text += 'The Specific Aims have not been modified from the original, competing application.\n\n'
            
        # Significance of the work
        markdown_text += '# Significance of the work\n\n'
        markdown_text += component['significance'] + '\n\n'

        # Significance of the work
        markdown_text += '# Product development milestones\n\n'
        if 'product_development_milestones' in component:
            markdown_text += component['product_development_milestones'] + '\n\n'
        else:
            markdown_text += 'This component does not have any product development milestones because it only supports the discovery stage.\n\n'

        # Significant Project-generated resources
        markdown_text += "# Significant Project-Generated Resources\n\n"
        # TODO
        #markdown_text += get_component_resources

    elif component['type'] == 'Core':
        #
        # Core-specific narrative (except for Administrative Core, which has text prepended manually)
        #
        
        # Individual Research Projects served and activities performed and/or completed
        markdown_text += "# Individual Research Projects served and activities performed and/or completed\n\n"
        if 'projects_served' in component:
            markdown_text += component['projects_served'] + '\n\n'
        # TODO: List activities performed and/or completed

        # Significant Core-generated resources (if any)
        markdown_text += "# Significant Core-Generated Resources\n\n"
        # TODO
        #markdown_text += get_component_resources

    # A. Specific Aims
    markdown_text += '# A. Specific Aims\n\n'
    if component['funded_aims_modified']:        
        markdown_text += component['aims'] + '\n\n'
    else:
        markdown_text += 'The Specific Aims have not been modified from the original, competing application.\n\n'

    # B. Studies and Results
    markdown_text += '# B. Studies and Results\n\n'
    markdown_text += 'Significant accomplishments include:\n\n'
    markdown_text += accomplishments[component_shortname] + '\n\n'
    markdown_text += f'Other major results and outputs from this {component["type"]} have been posted online and are listed in Significant Project-Generated Resources.\n\n'
    # TODO: Include statistics about Project and Core outputs

    # C. Significance
    markdown_text += '# C. Significance\n\n'
    markdown_text += component['significance'] + '\n\n'

    # D. Plans
    markdown_text += '# D. Plans\n\n'
    markdown_text += 'Plans for the next project period include:\n\n'
    markdown_text += plans[component_shortname] + '\n\n'

    # Human Subjects
    markdown_text += "# Human Subjects\n\n"
    markdown_text += 'Not Applicable\n\n'

    # Inclusion of Women and Minorities in Clinical Research
    markdown_text += "# Inclusion of Women and Minorities in Clinical Research\n\n"
    markdown_text += 'Not Applicable\n\n'

    # Human Subjects Education Requirement
    markdown_text += "# Human Subjects Education Requirement\n\n"
    markdown_text += 'Not Applicable\n\n'

    # Vertebrate Animals
    markdown_text += "# Human Subjects Education Requirement\n\n"
    if component.get('uses_vertebrate_animals', False):
        markdown_text += '----> **[INCLUDE VERTEBRATE ANIMALS SECTION]** <----\n\n'
    else:
        markdown_text += 'Not Applicable\n\n'

    # Select Agent Research
    markdown_text += "# Select Agent Research\n\n"
    markdown_text += 'Not Applicable\n\n'

    # Human Embryonic Stem Cell Line(s) Used
    markdown_text += "# Human Embryonic Stem Cell Line(s) Used\n\n"
    markdown_text += 'Not Applicable\n\n'

    # Publications (only in Administrative Core)
    if component_shortname == 'Administrative Core':
        markdown_text += "# Publications\n\n"

        publications = get_publications()

        if len(publications) == 0:
            markdown_text += "N/A\n\n"

        for publication in publications:
            # TODO: Check dates of publications and preprint/published version
            
            markdown_text += f"## {publication['title']}\n\n"
            markdown_text += f"*Authors:* {publication['authors']}\n\n"
            markdown_text += f"*Summary:* {publication['summary']}\n\n"
            if 'projects' in publication:
                markdown_text += f"*Contributing Projects:* " + ', '.join(publication['projects']) + "\n\n"
            if 'cores' in publication:
                markdown_text += f"*Contributing Cores:* " + ', '.join(publication['cores']) + "\n\n"
            if 'published' in publication:
                published = publication['published']
                if published['pages'] == 'in press':
                    markdown_text += f"*Publication {published['date']}:* *{published['journal']}* *in press* doi:{published['doi']}\n\n"
                    markdown_text += f"PMCID: This article is in press and has not yet received a PMCID.\n\n"
                else:
                    markdown_text += f"*Publication {published['date']}:* *{published['journal']}* **{published['volume']}**:{published['pages']}, {published['year']} doi:{published['doi']}\n\n"
                    markdown_text += f"PMCID: {published['pmcid']}\n\n"
            elif 'preprint' in publication:
                preprint = publication['preprint']
                markdown_text += f"*Preprint {preprint['date']}:* {preprint['server']} {preprint['url']}\n\n" 
                markdown_text += f"PMCID: This preprint has not yet been published.\n\n"
            

    # Project Generated Resources
    if component['type'] == 'Project':
        markdown_text += "# Project Generated Resources\n\n"
        # TODO: Include project-generated resources

    # Render markdown to document
    renderer = PythonDocxRenderer()
    render_code = MarkdownWithMath(renderer=renderer)(markdown_text)
    for index, line in enumerate(render_code.split('\n')):
        print(f'{index:8d}: {line}')
    exec(render_code)

    # Save the report
    import os
    output_filename = os.path.join(output_path, component_shortname + '.docx')
    document.save(output_filename)

    # Clean up
    if os.path.exists('tmp'):
        shutil.rmtree('tmp')

if __name__ == "__main__":

    # Retrieve Project and Core metadata
    components = get_components(yaml_filename='specific-aims.yaml')

    # Generate reports for all Projects and Cores
    import os
    output_path = 'outputs'
    os.makedirs(output_path, exist_ok=True)
    for component_shortname, component in components.items():
        # Skip the Administrative Core since this is a special case we are handling manually
        if component_shortname == 'Administrative Core':
            continue

        print(f"Generating report for {component['name']}")
        generate_progress_report(component_shortname, component, output_path)
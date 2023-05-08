"""
Generate the RPPR report for ASAP AViDD U19 year 1.

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

    # A. Specific Aims
    markdown_text += '# A. Specific Aims\n\n'
    if component['funded_aims_modified']:        
        markdown_text += component['aims'] + '\n\n'
    else:
        markdown_text += 'The Specific Aims have not been modified from the original, competing application.\n\n'

    # B. Studies and Results
    markdown_text += '# B. Studies and Results\n\n'
    markdown_text += accomplishments[component_shortname] + '\n\n'

    # C. Significance
    markdown_text += '# C. Significance\n\n'
    markdown_text += component['significance'] + '\n\n'

    # D. Plans
    markdown_text += '# D. Plans\n\n'
    markdown_text += plans[component_shortname] + '\n\n'

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
        print(f"Generating report for {component['name']}")
        generate_progress_report(component_shortname, component, output_path)
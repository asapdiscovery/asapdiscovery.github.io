"""
Generate the RPPR report for ASAP AViDD U19 year 1.

"""

def get_components():
    """
    Retrieve all component short and full names

    Returns
    -------
    components : dict of str : str
        components[short_name] is the long name of that component
    """
    # Read Specific Aims from YAML file 'specific-aims.yaml'
    import yaml
    specific_aims_filename = 'specific-aims.yaml'
    with open(specific_aims_filename, 'r') as f:
        specific_aims = yaml.load(f, Loader=yaml.SafeLoader)


    return specific_aims[component_name]


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

def generate_progress_report(component_shortname, component_longname, output_path):
    """
    Generate a project report for the specified Project or Core

    Parameters:
    -----------
    component_shortname : str
        Component short name key used in data tables
    component_longname : str
        Complete name to use in report
    output_path : str
        Name of output path to write report to.

    """

    # Use docx to generate Word documents on continuation pages directly.
    # See https://python-docx.readthedocs.io/
    import docx

    # Load the template and extract styles
    document = docx.Document("2590_continuation-template.docx")
    styles = document.styles
    from docx.enum.style import WD_STYLE_TYPE
    paragraph_styles = [
        s for s in styles if s.type == WD_STYLE_TYPE.PARAGRAPH
    ]
    for style in paragraph_styles:
        print(style.name)

    # Configure the header
    section = document.sections[0]
    header = section.header
    header.paragraphs[0].add_run('Chodera, John Damon').bold = True

    # Add component title
    document.add_heading(component_longname, 0)

    # Significant changes in the Specific Aims
    # TODO: Should we describe any changes in approach during the past year?
    document.add_heading("Significant changes in the Specific Aims", 1)
    if component['funded_aims_modified']:
        document.add_paragraph('The Specific Aims have been modified from the original, competing application as described in "A. Specific Aims" below.')
    else:
        document.add_paragraph('The Specific Aims have not been modified from the original, competing application.')
        
    # Significance of the work
    document.add_heading("Significance of the work")
    document.add_paragraph(component['significance'])
    
        
    document.add_paragraph(get_specific_aims(component_shortname))

    Discuss significance of Project in overall ASAP drug discovery pipeline
    Product development milestones
    Only P6, no Programs have reached P6 yet.
    Significant project-generated resources

    # A. Specific Aims
    document.add_heading("A. Specific Aims", 1)
    document.add_paragraph(get_specific_aims(component_shortname))

    # B. Studies and Results
    document.add_heading("B. Studies and Results", 1)
    # TODO

    # C. Significance
    document.add_heading("C. Significance", 1)
    # TODO

    # D. Plans


    document.add_heading("This is level 1 heading", 0)
    document.add_paragraph("This is a paragraph ")
    document.add_heading("This is level 2 heading", 1)
    document.add_paragraph("This is a paragraph")
    document.add_heading("This is level 3 heading", 2)
    paragraph = document.add_paragraph("This is a paragraph")
    paragraph.add_run(" this is a section at the end of third paragraph")

    document.add_paragraph('This is a caption', style='Caption')

    document.add_paragraph(
        'First item in unordered list', style='List Bullet'
    )

    document.add_paragraph(
        'First item in ordered list', style='List Number'
    )
    document.add_paragraph(
        'Second item in ordered list', style='List Number'
    )

    # Save the report
    import os
    output_filename = os.path.join(output_path, component_name + '.docx')
    document.save(output_filename)


# Retrieve list of component short and long names
components = get_components()

# Generate reports
import os
output_path = 'outputs'
os.makedirs(output_path, exist_ok=True)
for component_shortname, component_longname in components.items():
    print(f'Generating report for {component_shortname} : {component_longname}')
    generate_progress_report(component_shortname, component_longname, output_path)
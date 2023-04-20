# See https://python-docx.readthedocs.io/

import docx

document = docx.Document("2590_continuation.docx")
styles = document.styles
from docx.enum.style import WD_STYLE_TYPE
paragraph_styles = [
    s for s in styles if s.type == WD_STYLE_TYPE.PARAGRAPH
]
for style in paragraph_styles:
    print(style.name)

section = document.sections[0]
header = section.header
header.paragraphs[0].add_run('Chodera, John Damon').bold = True

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

document.save("output.docx")
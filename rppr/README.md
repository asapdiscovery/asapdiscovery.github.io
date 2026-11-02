# Scripts for generating NIH RPPR Progress Report Summary

These scripts automate the generation of the Progress Report Summary (PHS 2590 Form Page 5 continuation pages) for each Project and Core of the ASAP AViDD U19 Center.

All styles are taken from the `2590_continuation-template.docx` template. Modifications to this document will be propagated through into generated Word documents.

## Prerequisites

```bash
conda env create -f environment.yml   # or: conda env update -n rppr -f environment.yml
conda activate rppr
```

## RPPR generation

Each Project/Core writes its narrative sections (**B. Studies and Results**, **C. Significance**, **D. Plans**) as a Word document named `<Component>*.docx` (e.g. `Project 6.docx`, `Antiviral Core.docx`) in a shared Google Drive folder. The script combines, for each component in `specific-aims.yaml`:

1. generated front matter and **A. Specific Aims** (from `specific-aims.yaml`; the Administrative Core document may supply its own overall narrative and Specific Aims)
2. the B/C/D narrative from the Drive document (figures, tables, and formatting preserved; leftover template instructions and comments are stripped)
3. a generated **Publications and research outputs during this reporting period** subsection at the end of B, drawn from the Hugo data in `../data` (publications/preprints, research outputs, TEP resources, software, protocols, ChEMBL datasets)
4. generated compliance sections (Human Subjects, Vertebrate Animals, ...)

```bash
python generate-rppr.py                               # default Drive folder, writes outputs/
python generate-rppr.py --drive-sections DIR          # use a different folder (e.g. a downloaded zip)
python generate-rppr.py --components "Project 6"      # regenerate a single component
python generate-rppr.py --period-start 2025-09-19 --period-end 2026-12-31
```

Generated Word documents are written to `outputs/` (close them in Word first), along with `outputs/rppr-issues.md`, which lists problems to resolve: missing Drive documents or sections, unresolved comments, leftover template text, figures/tables lost in the merge, outputs without attribution, publications without PMCIDs, etc.

If no Drive document is found for a component, the legacy `asap-year-1-accomplishments.yaml` / `asap-year-1-plans.yaml` text is used and flagged as an error.

## Checking reportable outputs

```bash
python check-outputs.py [--slides outputs-overview-slides.pdf] [--offline]
```

Extracts hyperlinks from the outputs overview slide deck and checks that each is represented in the Hugo data; queries bioRxiv/chemRxiv/Crossref/NCBI to verify preprint first-posted dates, version history, published versions, and PMCIDs; and flags attribution names that do not match a component. Writes `outputs/outputs-audit.md`.

### Publication date conventions (`../data/publications/publications.yaml`)

* `preprint.date`: date the **first** version was posted
* `preprint.versions`: optional list of `{version, date, url}` for every posted version; later versions within the reporting period are reported as "preprint updated"
* `published.date`: online publication date of the journal version

Research outputs in `../data/outputs/*.yaml` are reported when they have a dated `events` entry in the reporting period (software, molecules, ...); protocols use `date`, ChEMBL datasets use `released`, and TEP resources use `date`.

## Manifest
* `specific-aims.yaml` : Names, Specific Aims, and generic significance text for Projects and Cores
* `asap-year-1-accomplishments.yaml`, `asap-year-1-plans.yaml` : legacy B/D text (fallback only)
* `generate-rppr.py` : report generator
* `check-outputs.py` : outputs audit

## Thumbnail videos

To generate a thumbnail sheet of youtube videos:
```bash
python3 -m pip install -U yt-dlp Pillow requests
python3 avidd_thumbnail_sheet.py
```

---

Beanan, Maureen (NIH/NIAID) [E] <beananm@mail.nih.gov>
Attachments
Thu, Mar 2, 8:42 AM
to me, choderaj@mskcc.org, Maggie, jamesom1@mskcc.org, Weibertt@mskcc.org, sponsorp@mskcc.org

Dear John, Theresa, and Maggie

NIH has identified issues with the submission of Multi-Year Funded Research Performance Progress Reports (RPPRs) using the eRA Commons, consequently all AViDD awardees must now use the PHS 2590 format instead of the eRA Commons to prepare and submit the Annual Progress Report for Year 1.   Please disregard the instructions previously transmitted via the email sent in November 2022. 

Please see the attached instructions for the PHS 2590 format and the Revised AViDD Progress Report Guidelines.  The additional information being requested in the Revised AViDD Progress Report Guidelines is the same as the previous version, however, for the PHS 2590 format you will now provide this information using Form page 5 instead of sections noted in the previous version.

The PHS 2590 forms can be downloaded from: https://grants.nih.gov/grants/funding/2590/2590.htm

The Annual Progress Report will contain separate reports for each component of your AViDD.   You will create a separate PHS 2590 report for the AViDD Overall progress, each Research Project, and each Core, and these will be combined to generate the Annual Progress Report.

The separate reports for each component will contain:
* Form Page 1:  Face Page – leave Items 8a and 8b blank
    * Form Page 1-continued:  Additional form if Multiple PIs are involved
* Project/Performance Site Format Page - use only if additional space is needed
* Biographical Sketch: Complete a Biographical Sketch for all new senior/key personnel since the previous submission.  Use form available from https://grants.nih.gov/grants/forms/biosketch.htm
* Other Support: Include other active support for all senior/key personnel whose support has changed during the past year and indicate what the change has occurred.  Use form available from https://grants.nih.gov/grants/forms/othersupport.htm
* Form Page 5:  Progress Report Summary - this form will be used to provide both the additional information required for AViDD awards as well as the standard information required for a Progress Report.  Please refer to the Revised AViDD Progress Report Guidelines for the additional information required to be included in the Progress Summary for the AViDD Overall, Research Project and Core reports.
    * Use the Continuation page after Form page 5 is full for this section and any other sections that require additional pages after the initial form.
* Form Page 6:  Checklist
* Form Page 7:  All Personnel Report
* If Human Subjects Research is being conducted - include the PHS Inclusion Enrollment Report

Please refer to the attached Revised AViDD Progress Report Guidelines and the phs2590 General Instructions found on pages 5 through 17 for guidance about the information required for each section.

Because your AViDD award is a Multi-Year Funded award you are not required to submit Detailed Budget for Next Budget Period or Budget Justification pages as part of the Annual Progress Report.  In addition, carry forward requests are not required during the remaining time of the Multi-Year Funded project period.   However, if the situation arises, please note, prior approval is still required for compliance with the significant rebudgeting policy as stated in the NIH Grants Policy Statement https://grants.nih.gov/policy/nihgps/index.htm:

Significant rebudgeting, whether or not the particular expenditure(s) require prior approval:  Significant rebudgeting occurs when expenditures in a single direct cost budget category deviate (increase or decrease) from the categorical commitment level established for the budget period by 25 percent or more of the total direct costs awarded. For example, if the award budget for total direct costs is $200,000, any rebudgeting that would result in an increase or decrease of more than $50,000 in a budget category is considered significant rebudgeting

To submit the report, your Authorized Institutional Official will email the entire Annual Progress Report to Bianca Steele, who is the NIAID Grants Management Official for this award, and me.

These reports are due by the project anniversary date (05/16/2023) for your award and can be submitted anytime between now and then.  
As noted above, please read through the Revised AViDD Report Guidelines and the PHS 2590 instructions.  If questions remain, then please have your business official contact Bianca Steele and me.

We apologize for the inconvenience.

Sincerely yours,

Maureen

 

Maureen Beanan, Ph.D.

Program Officer

Translational Centers of Excellence and Research Coordination Section

Office of Biodefense, Research resources, and Translational Research

DMID/NIAID/NIH
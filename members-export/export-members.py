"""
Python script to convert CSV file to Member YAML files

Input: CSV file with member information
CSV header format: Onboarding complete?,Name,Core/Project,Grant role,Tags/Expertise,Time Zone,Main Email,Pronouns,Phone Number,GitHub username,Accessible travel,Onboarding Page,Shipping address,Photo,Google Drive Email,Date of Birth (MM/YYYY),Degree (highest),SSN (last 4 digits),eRA Commons ID,Year 1 Calendar effort (Pending collection),First Name,Last Name,Photo filename,ORCID,Affiliation,Created by,Attending NY Meeting

YAML entry format example :

name: John D. Chodera
role: "Principal Investigator; Co-Investigator: Hit-to-Lead; Co-Investigator: Lead Optimization"
lab: Chodera lab
title: Associate Member
institution: Sloan Kettering Institute
img: john-chodera.jpg
webpage: "http://choderalab.org"
description: Contact PI; Oversight of cores; Alchemical free energy calculations on [Folding@home](http://foldingathome.org); computational chemistry and structure-based machine learning
google_scholar: http://goo.gl/qO0JW
ORCID: 0000-0003-0542-119X
twitter: jchodera
github: jchodera
"""

# Open the CSV
csv_filename = "ASAP Member Directory 29163cfc67e144b389e475acaddf14ad.csv"
import csv
csv_contents = csv.DictReader(open(csv_filename, 'r'))

def imgify(name):
    """Convert name to lowercase characters and replace spaces with dashes"""
    return name.lower().replace(' ', '-') + '.jpg'

# Get list of existing members by reading YAML files in '../data/members/'
import glob
import os
existing_members = [os.path.basename(f).replace('.yaml', '').replace('_', ' ') for f in glob.glob('../data/members/*.yaml')]

print(existing_members)

# Write YAML files
members = list()
for csv_member in csv_contents:
    if csv_member['\ufeffOnboarding complete?'] != 'Yes':
        continue

    try:
        lastname, firstname = csv_member['Name'].split(',')
        name = firstname.strip() + ' ' + lastname.strip()

        # Skip if member already exists
        if name in existing_members:
            continue

        member = {
            'name' : name,
            'role' : csv_member['Grant role'],
            'lab' : csv_member['Core/Project'],
            'title' : csv_member['Grant role'],
            'institution' : csv_member['Affiliation'],
            'img' : imgify(name),
            'description' : csv_member['Grant role'],
            'ORCID' : csv_member['ORCID'],
            'github' : csv_member['GitHub username'],
        }

        # Delete empty fields
        for key, value in list(member.items()):
            if value == '':
                del member[key]

        # Write YAML file
        import os
        import yaml
        safe_name = "_".join( name.split() )
        yaml_filename = os.path.join('output', safe_name + '.yaml')
        yaml.dump(member, open(yaml_filename, 'w'), default_flow_style=False)

        print(name)
                
    except ValueError as e:
        pass


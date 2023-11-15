import csv
import re
import logging
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(filename='compare_manifest.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def load_rules(filename):
    rules = {}
    with open(filename, 'r') as file:
        for line in file:
            pattern, replace = line.strip().split(' > ')
            logging.info(f"Loaded rule: {pattern} > {replace}")
            
            # Replace spaces between alphanumeric boundaries with dashes
            pattern = re.sub(r'([a-z]) (\d)', r'\1-\2', pattern)
            pattern = re.sub(r'(\d) ([a-z])', r'\1-\2', pattern)
            replace = re.sub(r'([a-z]) (\d)', r'\1-\2', replace)
            replace = re.sub(r'(\d) ([a-z])', r'\1-\2', replace)
            
            # Insert dashes between alphanumeric boundaries (without spaces)
            pattern = re.sub(r'([a-z])(\d)', r'\1-\2', pattern)
            pattern = re.sub(r'(\d)([a-z])', r'\1-\2', pattern)
            replace = re.sub(r'([a-z])(\d)', r'\1-\2', replace)
            replace = re.sub(r'(\d)([a-z])', r'\1-\2', replace)
            
            # Replace spaces with dashes in the replacement pattern
            replace = replace.replace(' ', '-')
            
            rules[pattern] = replace
    return rules

def extract_three_digit_number(section):
    matches = re.findall(r'\w(\d{3})\w', section)
    return matches[0] if matches else None    

def normalize_section_name(section):
    """
    Apply basic normalization to the section name.
    """
    original_section = section
    section = section.lower()
    section = re.sub(r'([a-z])(\d)', r'\1-\2', section)
    section = re.sub(r'(\d)([a-z])', r'\1-\2', section)
    section = re.sub(r'section', '', section).strip()

    abbreviations = {
        'flr': 'floor',
        'orch': 'orchestra',
        'blch': 'bleacher',
        'fd': 'field',
        'balc': 'balcony',
        'rgt': 'right',
        'lft': 'left',
        'frn': 'front',
        'ctr': 'center'
    }
    for abbr, full in abbreviations.items():
        section = section.replace(abbr, full)
    
    if original_section != section:
        logging.info(f"Normalized '{original_section}' to '{section}'")
    
    return section

def apply_rules(section, rules, all_sections):
    """
    Apply transformation rules to the section name.
    """
    original_section = section

    # Apply hardcoded normalization
    section = normalize_section_name(section)

    # Check for a unique three-digit number
    three_digit_num = extract_three_digit_number(section)
    if three_digit_num:
        matching_sections = [s for s in all_sections if three_digit_num in s]
        if len(matching_sections) == 1:
            return matching_sections[0]

    # Apply custom rules from the rules.txt
    for pattern, replacement in rules.items():
        if re.search(pattern, section):
            section = re.sub(pattern, replacement, section)
            logging.info(f"Applied rule on '{original_section}': {pattern} > {replacement}. Result: '{section}'")

    if section != original_section and section in all_sections:
        logging.info(f"Final transformation for '{original_section}' is '{section}'")

    return section

def load_csv(filename, rules, all_sections=None, analyze_seat_level=True):
    data = {}
    
    with open(filename, 'r') as f:
        # Splitting manually on newline and comma
        rows = [line.strip().split(',') for line in f.readlines()]

        # Extracting header from the first row and normalizing to lowercase
        headers = [header.lower() for header in rows[0]]
        
        # Check if headers are as expected
        expected_headers = ['section', 'row']
        if 'seat' in headers:
            expected_headers.append('seat')

        # Iterate over the rows (excluding header)
        for row in rows[1:]:
            if not row or len(row) < 2 or row[0] == '':
                continue
            row_data = dict(zip(headers, map(lambda x:x.lower(), row)))
            section = apply_rules(row_data['section'], rules, all_sections)
            
            if 'seat' in headers and analyze_seat_level:
                if section not in data:
                    data[section] = {}
                
                # Convert the row name to lowercase
                row_name_lower = row_data['row'].lower()
                
                if row_name_lower not in data[section]:
                    data[section][row_name_lower] = []
                data[section][row_name_lower].append(row_data['seat'])
            else:
                if section not in data:
                    data[section] = set()
                data[section].add(row_data['row'].lower())

    return data



def compare_manifests(mine, client):
    differences = []
    df = pd.DataFrame({'sg-section':[], 'sg-row':[], 'sg-seats':[], 'client-section':[], 'client-row':[], 'client-seats':[]})

    # Check if comparison is seat-level or row-level
    is_seat_level = all(isinstance(val, dict) for val in mine.values())

    if is_seat_level:
        # Seat-level comparison logic
        matched_sections = set()  # To track sections that matched
        
        for section in mine:
            if section not in client:
                differences.append(f"section {section} missing in client's manifest")
                new_row = {'client-section':section}
                df.loc[len(df)] = new_row
                continue
            matched_sections.add(section)
            for row in mine[section]:
                row_lower = row.lower()
                if row_lower not in client[section]:
                    differences.append(f"section {section}, row {row} missing in client's manifest")

                    new_row = {'client-section':section, 'client-row':row}
                    df.loc[len(df)] = new_row
                    continue

                missing_in_mine = set(client[section][row_lower]) - set(mine[section][row])
                missing_in_client = set(mine[section][row]) - set(client[section][row_lower])

                if missing_in_mine:
                    missing_in_mine_sorted_seats = sorted([str(e) for e in missing_in_mine])
                    differences.append(f"In section {section}, row {row}, client's manifest has seats {', '.join(missing_in_mine_sorted_seats)} that are not in SeatGeek Manifest.")

                    new_row = {'sg-section':section, 'sg-row':row, 'sg-seats':', '.join(missing_in_mine_sorted_seats)}
                    df.loc[len(df)] = new_row

                if missing_in_client:
                    missing_in_client_sorted_seats = sorted([str(e) for e in missing_in_client])
                    differences.append(f"In section {section}, row {row}, SeatGeek Manifest has seats {', '.join(missing_in_client_sorted_seats)} that are not in client's manifest.")

                    new_row = {'client-section':section, 'client-row':row,'client-seats':', '.join(missing_in_client_sorted_seats)}
                    df.loc[len(df)] = new_row
            
            for row in client[section]:
                if row not in mine[section]:
                    differences.append(f"In section {section}, row {row} missing in SeatGeek Manifest")
                    new_row = {'sg-section':section, 'sg-row':row}
                    df.loc[len(df)] = new_row
                
        unmatched_sections = set(client.keys()) - matched_sections
        for section in unmatched_sections:
            differences.append(f"section {section} missing in SeatGeek Manifest")
            new_row = {'sg-section':section}
            df.loc[len(df)] = new_row

    else:
        # Row-level comparison logic
        missing_sections_in_mine = set(client.keys()) - set(mine.keys())
        missing_sections_in_client = set(mine.keys()) - set(client.keys())

        for section in missing_sections_in_mine:
            differences.append(f"section {section} missing in SeatGeek Manifest")

            new_row = {'sg-section':section}
            df.loc[len(df)] = new_row

        for section in missing_sections_in_client:
            differences.append(f"section {section} missing in client's manifest")

            new_row = {'client-section':section}
            df.loc[len(df)] = new_row

        for section, rows in mine.items():
            if section in client:
                missing_rows_in_mine = client[section] - rows
                missing_rows_in_client = rows - client[section]

                for row in missing_rows_in_mine:
                    differences.append(f"In section {section}, row {row} missing in SeatGeek Manifest")

                    new_row = {'sg-section':section, 'sg-row':row}
                    df.loc[len(df)] = new_row

                for row in missing_rows_in_client:
                    differences.append(f"In section {section}, row {row} missing in client's manifest")

                    new_row = {'client-section':section, 'client-row':row}
                    df.loc[len(df)] = new_row
    
    df = df.fillna('')
    print(df)
    sg_df = client_df = None
    if is_seat_level:
        sg_df = df[['sg-section', 'sg-row', 'sg-seats']].loc[(df['sg-section'] != '') | (df['sg-row'] != '') | (df['sg-seats'] != '')].sort_values(by=['sg-section', 'sg-row'])
        client_df = df[['client-section', 'client-row', 'client-seats']].loc[(df['client-section'] != '') | (df['client-row'] != '') | (df['client-seats'] != '')].sort_values(by=['client-section', 'client-row'])
    else:
        sg_df = df[['sg-section', 'sg-row']].loc[(df['sg-section'] != '') | (df['sg-row'] != '')].sort_values(by=['sg-section', 'sg-row'])    
        client_df = df[['client-section', 'client-row']].loc[(df['client-section'] != '') | (df['client-row'] != '')].sort_values(by=['client-section', 'client-row'])

    sg_count = sg_df['sg-section'].count()
    client_count = client_df['client-section'].count()
    df = df.sort_values(by=['sg-section','sg-row','client-section', 'client-row'])

    return (sg_df.to_html(index=False), client_df.to_html(index=False), sg_count, client_count, df.to_csv(index=False))

if __name__ == "__main__":
    logging.info("Script started.")

    rules = load_rules('rules.txt')
    seatgeek_manifest_sections = set()
    
    with open('temp_seatgeek.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Making it case-insensitive
            section_value = row.get('SECTION', row.get('section', '')).lower()
            seatgeek_manifest_sections.add(section_value)
            
    seatgeek_manifest = load_csv('temp_seatgeek.csv', rules, seatgeek_manifest_sections)
    client_manifest = load_csv('temp_client.csv', rules, seatgeek_manifest_sections)
    
    differences = compare_manifests(seatgeek_manifest, client_manifest)

    with open('differences.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(["Difference"])
        for diff in differences:
            writer.writerow([diff])

    logging.info("Script finished. Results written to 'differences.csv'")
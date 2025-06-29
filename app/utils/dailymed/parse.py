"""
DailyMed Parsing Module

Provides functions for parsing HTML content from DailyMed.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any, Set
from bs4 import BeautifulSoup, Tag
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("app.utils.dailymed.parse")

# Define constants for section identification

# List of important clinical sections to extract
IMPORTANT_CLINICAL_SECTIONS = [
    "BOXED WARNING",
    "INDICATIONS AND USAGE",
    "DOSAGE AND ADMINISTRATION",
    "DOSAGE FORMS AND STRENGTHS",
    "CONTRAINDICATIONS",
    "WARNINGS AND PRECAUTIONS",
    "ADVERSE REACTIONS",
    "USE IN SPECIFIC POPULATIONS",
    "DESCRIPTION",
    "CLINICAL PHARMACOLOGY",
    "NONCLINICAL TOXICOLOGY",
    "CLINICAL STUDIES", 
    "HOW SUPPLIED/STORAGE AND HANDLING",
    "PATIENT COUNSELING INFORMATION",
    "DRUG INTERACTIONS",
    "WARNINGS"
]

# Table sections of interest
IMPORTANT_TABLE_SECTIONS = [
    "Product Information",
    "Active Ingredient/Active Moiety",
    "Inactive Ingredients",
    "Product Characteristics", 
    "Packaging",
    "Marketing Information"
]

# Precompiled regex patterns and heading tags
ACTIVE_INGREDIENT_PATTERN = re.compile(r'ACTIVE\s+INGREDIENT', re.IGNORECASE)
INACTIVE_INGREDIENT_PATTERN = re.compile(r'INACTIVE\s+INGREDIENT', re.IGNORECASE)
NDC_REGEX = re.compile(r'\b\d{4,5}-\d{3,4}-\d{1,2}\b')
HEADING_TAGS = ['h1', 'h2', 'h3', 'h4']


def extract_basic_info(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract basic drug information from DailyMed HTML.
    
    Args:
        soup: BeautifulSoup object of the drug page
        
    Returns:
        Dictionary with extracted information
    """
    data = {}
    
    try:
        # Extract title
        title_elem = soup.select_one('.drug-title') or soup.select_one('h1') or soup.select_one('title')
        if title_elem:
            title = title_elem.get_text(strip=True)
            title = title.split(':',1)[-1].strip()  # remove "Label:" prefix
            data['title'] = title
            logger.debug(f"Extracted title: {data['title']}")
    except Exception as e:
        logger.error(f"Error extracting title: {str(e)}")
    
    try:
        # Extract manufacturer using multiple approaches
        # Approach 1: Look for elements with specific classes
        manufacturer = None
        for selector in ['.manufacturer', '.applicant', '.labeler', '.company', '.sponsor']:
            manu_elem = soup.select_one(selector)
            if manu_elem:
                manufacturer = manu_elem.get_text(strip=True)
                if manufacturer:
                    break
        # Approach 2: Look for text with manufacturer indicators
        if not manufacturer:
            # Look for manufacturer in "Manufactured by", "Marketed by", etc.
            for section in soup.find_all(['div', 'p', 'span']):
                text = section.get_text(strip=True).lower()
                for indicator in ['manufactured by', 'marketed by', 'distributed by', 'applicant']:
                    if indicator in text:
                        idx = text.find(indicator) + len(indicator)
                        manufacturer = text[idx:idx+100].strip()
                        if manufacturer:
                            # Clean up - take only up to the first period or newline
                            end_idx = min(
                                manufacturer.find('.') if manufacturer.find('.') > 0 else len(manufacturer),
                                manufacturer.find('\n') if manufacturer.find('\n') > 0 else len(manufacturer)
                            )
                            manufacturer = manufacturer[:end_idx].strip()
                            break
                if manufacturer:
                    break
        # Fallback: look in list items for Packager
        packager = None
        for li in soup.select('li'):
            text = li.get_text(strip=True)
            if text.startswith('Packager:'):
                packager = text.split(':',1)[1].strip()
                break
        # Use packager if it's valid or if original manufacturer is clearly malformed
        if packager and (not manufacturer or ':' in manufacturer or len(manufacturer.split())<3):
            manufacturer = packager
        if manufacturer:
            data['manufacturer'] = manufacturer
            logger.debug(f"Extracted manufacturer: {manufacturer}")
    except Exception as e:
        logger.error(f"Error extracting manufacturer: {str(e)}")
    
    try:
        # Extract active ingredients
        active_ingredients = []
        ingredients_section = None
        
        # Find sections that might contain active ingredients
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            if any(x in heading.get_text().lower() for x in ['active ingredient', 'composition']):
                ingredients_section = heading.find_next(['div', 'p', 'ul', 'table'])
                break
        
        if ingredients_section:
            # Extract from tables
            tables = ingredients_section.find_all('table')
            if tables:
                for table in tables:
                    for row in table.find_all('tr')[1:]:  # Skip header row
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            ingredient = cells[0].get_text(strip=True)
                            strength = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                            if ingredient:
                                active_ingredients.append({
                                    'name': ingredient,
                                    'strength': strength
                                })
            
            # Extract from text if no table found
            if not active_ingredients:
                text = ingredients_section.get_text(strip=True)
                # Look for common patterns like "ingredient (strength)"
                ingredient_matches = re.findall(r'([A-Za-z\s\-]+)\s*\(([^)]+)\)', text)
                for name, strength in ingredient_matches:
                    active_ingredients.append({
                        'name': name.strip(),
                        'strength': strength.strip()
                    })
        
        if active_ingredients:
            data['active_ingredients'] = active_ingredients
            logger.debug(f"Extracted {len(active_ingredients)} active ingredients")
    except Exception as e:
        logger.error(f"Error extracting active ingredients: {str(e)}")
    
    try:
        # Extract drug class
        class_section = None
        # Find drug class information
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            if any(x in heading.get_text().lower() for x in ['drug class', 'pharmacologic class', 'therapeutic class']):
                class_section = heading.find_next(['div', 'p', 'ul'])
                break
        if class_section:
            class_text = class_section.get_text(strip=True)
            class_text = re.sub(r'\s+', ' ', class_text)
            data['drug_class'] = class_text
            logger.debug(f"Extracted drug class: {class_text}")
        # Extract Drug Class from Category
        for li in soup.select('li'):
            text = li.get_text(strip=True)
            if text.startswith('Category:'):
                data['drug_class'] = text.split(':',1)[1].strip()
                logger.debug(f"Extracted drug class from Category: {data['drug_class']}")
                break
    except Exception as e:
        logger.error(f"Error extracting drug class: {str(e)}")
    
    try:
        # Extract set ID
        set_id_elem = soup.select_one('.setid') or soup.find(string=re.compile(r'Set ID:'))
        if set_id_elem:
            if isinstance(set_id_elem, Tag):
                set_id = set_id_elem.get_text(strip=True).replace('Set ID:', '').strip()
            else:
                set_id = re.search(r'Set ID:\s*([a-zA-Z0-9\-]+)', str(set_id_elem))
                set_id = set_id.group(1) if set_id else None
                
            if set_id:
                data['set_id'] = set_id
                logger.debug(f"Extracted set ID: {set_id}")
    except Exception as e:
        logger.error(f"Error extracting set ID: {str(e)}")
    
    try:
        # Extract NDC codes from More Info section list items
        ndc_codes = []
        # find the li containing "NDC Code"
        ndc_li = soup.find('li', string=re.compile(r'NDC Code'))
        if ndc_li:
            texts = [ndc_li.get_text()]
            sib = ndc_li.find_next_sibling('li')
            # capture following lists until Packager
            while sib and not sib.get_text().startswith('Packager:'):
                texts.append(sib.get_text())
                sib = sib.find_next_sibling('li')
            combined = ' '.join(texts)
            ndc_codes = NDC_REGEX.findall(combined)
        if ndc_codes:
            data['ndc_codes'] = ndc_codes
            logger.debug(f"Extracted {len(ndc_codes)} NDC codes")
    except Exception as e:
        logger.error(f"Error extracting NDC codes: {str(e)}")

    # Fallback: scan table cells for NDC patterns
    if 'ndc_codes' not in data:
        ndc_codes = []
        for td in soup.select('td.formItem'):
            codes = NDC_REGEX.findall(td.get_text(strip=True))
            ndc_codes.extend(codes)
        if ndc_codes:
            data['ndc_codes'] = ndc_codes
            logger.debug(f"Extracted {len(ndc_codes)} NDC codes from tables")
    
    try:
        # Extract download links
        downloads = {}
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if href and any(ext in href.lower() for ext in ['.pdf', '.xml', '.zip']):
                if text:
                    downloads[text] = href
                else:
                    file_type = href.split('.')[-1].upper()
                    downloads[f"{file_type} Download"] = href
        
        if downloads:
            data['downloads'] = downloads
            logger.debug(f"Extracted {len(downloads)} download links")
    except Exception as e:
        logger.error(f"Error extracting download links: {str(e)}")

    # Extract set_id from RSS link if not already found
    if 'set_id' not in data or not data.get('set_id'):
        rss_link = None
        for link in soup.find_all('a', href=True):
            if 'labelrss.cfm?setid=' in link['href']:
                rss_link = link['href']
                break
        if rss_link:
            query = urlparse(rss_link).query
            params = parse_qs(query)
            if 'setid' in params:
                data['set_id'] = params['setid'][0]
                logger.debug(f"Extracted set ID from RSS link: {data['set_id']}")
    
    return data


def extract_full_sections(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract all text sections from DailyMed HTML.
    
    Args:
        soup: BeautifulSoup object of the drug page
        
    Returns:
        Dictionary mapping section headings to content
    """
    sections = {}

    # Capture Boxed Warning section if present in HTML
    boxed = soup.find('div', class_='boxedWarning')
    if boxed:
        sections['BOXED WARNING'] = boxed.get_text(separator='\n', strip=True)

    # Handle preformatted text blocks with tab-delimited tables
    pre_blocks = soup.find_all('pre')
    pre_sections = {}
    for pre in pre_blocks:
        text = pre.get_text().strip()
        lines = text.splitlines()
        # Only process blocks that appear tab-delimited
        if len(lines) > 1 and '\t' in lines[0]:
            heading = lines[0]
            content = '\n'.join(lines[1:])
            pre_sections[heading] = content
    # Try multiple selectors for section containers
    section_selectors = ['.Section', '.section', '#content', '.content', 'main']
    section_divs = []
    for sel in section_selectors:
        section_divs = soup.select(sel)
        if section_divs:
            break

    # Process each found section div
    for section in section_divs:
        # Extract heading
        heading_elem = section.find(HEADING_TAGS) or section.find(class_=re.compile(r'heading|title', re.I))
        if heading_elem:
            heading = heading_elem.get_text(strip=True)
        else:
            content_text = section.get_text(strip=True)
            heading = (content_text[:30] + "...") if len(content_text) > 30 else content_text

        # Extract content - exclude the heading
        content = ""
        for element in section.find_all(['p', 'div', 'span', 'ul', 'ol', 'table']):
            if not element.find_parent(['table']):
                text = element.get_text(strip=True)
                if text:
                    content += text + "\n\n"
        if heading and content:
            sections[heading] = content.strip()
    
    # If no sections found using the main approach, try a generic approach
    if not sections:
        try:
            # Look for any content div with reasonable structure
            content_div = soup.select_one('#content') or soup.select_one('.content') or soup.select_one('main')
            
            if content_div:
                # Find all headings and associate with following content
                current_heading = None
                current_content = []
                
                for element in content_div.find_all(HEADING_TAGS + ['p', 'div', 'span', 'ul', 'ol']):
                    # Check if this is a heading
                    if element.name in HEADING_TAGS:
                        # Save previous section if exists
                        if current_heading and current_content:
                            sections[current_heading] = '\n\n'.join(current_content)
                            current_content = []
                        
                        current_heading = element.get_text(strip=True)
                    elif current_heading and element.name in ['p', 'div', 'span', 'ul', 'ol']:
                        # Add content to current section
                        text = element.get_text(strip=True)
                        if text and len(text) > 10:  # Ignore very short fragments
                            current_content.append(text)
                
                # Save the last section
                if current_heading and current_content:
                    sections[current_heading] = '\n\n'.join(current_content)
        except Exception as e:
            logger.error(f"Error using generic section extraction: {str(e)}")
    
    # Plain-text fallback: attempt to split on lines ending with a colon as headings
    if not sections:
        raw_text = soup.get_text(separator="\n")
        text = raw_text.strip()
        current_heading = None
        current_content = []
        for line in text.splitlines():
            # Support uppercase-only headings (short, all uppercase lines)
            if line.strip() and line.strip().isupper() and len(line.split()) < 10:
                # Save previous section
                if current_heading and current_content:
                    sections[current_heading] = "\n".join(current_content).strip()
                current_heading = line.strip()
                current_content = []
                continue
            # Consider lines ending with ':' as section headings
            if re.match(r'^[A-Za-z0-9 \-\/%&\(\)]+:\s*$', line):
                # Save previous section
                if current_heading and current_content:
                    sections[current_heading] = "\n".join(current_content).strip()
                # New heading without trailing colon
                current_heading = line.rstrip(':').strip()
                current_content = []
            elif current_heading:
                # Accumulate content lines
                if line.strip():
                    current_content.append(line)
        # Save the last section
        if current_heading and current_content:
            sections[current_heading] = "\n".join(current_content).strip()
    logger.debug(f"Extracted {len(sections)} sections")
    return sections


def extract_ingredients(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
    """
    Extract active and inactive ingredients from DailyMed HTML.
    
    Args:
        soup: BeautifulSoup object of the drug page
        
    Returns:
        Tuple of (active_ingredients, inactive_ingredients) lists
    """
    active_ingredients = []
    inactive_ingredients = []

    # Class-based extraction for Active and Inactive Ingredients
    for table in soup.select('table.formTablePetite, table.formTableMorePetite'):
        header_cell = table.find('td', class_='formHeadingTitle')
        if not header_cell:
            continue
        heading_text = header_cell.get_text(strip=True).lower()
        # Active ingredients table
        if 'active ingredient/active moiety' in heading_text:
            for row in table.select('tr.formTableRow, tr.formTableRowAlt'):
                cells = row.find_all('td', class_='formItem')
                if len(cells) >= 3:
                    name = cells[0].get_text(strip=True)
                    if name.upper().startswith('NDA'):
                        continue
                    strength = cells[2].get_text(strip=True)
                    active_ingredients.append(f"{name} {strength}".strip())
        # Inactive ingredients table
        elif 'inactive ingredients' in heading_text:
            for row in table.select('tr.formTableRow, tr.formTableRowAlt'):
                cells = row.find_all('td', class_='formItem')
                if cells:
                    name = cells[0].get_text(strip=True)
                    if name.upper().startswith('NDA'):
                        continue
                    inactive_ingredients.append(name)
    # If both lists populated, return early
    if active_ingredients and inactive_ingredients:
        # Deduplicate before returning
        # Deduplicate ingredients
        active_ingredients = list(dict.fromkeys([clean_ingredient_name(i) for i in active_ingredients]))
        inactive_ingredients = list(dict.fromkeys([clean_ingredient_name(i) for i in inactive_ingredients]))
        return active_ingredients, inactive_ingredients

    # Clean and deduplicate the ingredient lists
    active_ingredients = deduplicate_and_clean_ingredients(active_ingredients)
    inactive_ingredients = deduplicate_and_clean_ingredients(inactive_ingredients)

    # Deduplicate ingredients
    active_ingredients = list(dict.fromkeys([clean_ingredient_name(i) for i in active_ingredients]))
    inactive_ingredients = list(dict.fromkeys([clean_ingredient_name(i) for i in inactive_ingredients]))
    
    # Fallback: parse DESCRIPTION section if no ingredients found
    if not active_ingredients and not inactive_ingredients:
        desc = extract_full_sections(soup).get('DESCRIPTION', "")
        if desc:
            extract_ingredients_from_text(desc, active_ingredients, inactive_ingredients)
            active_ingredients = deduplicate_and_clean_ingredients(active_ingredients)
            inactive_ingredients = deduplicate_and_clean_ingredients(inactive_ingredients)
    logger.debug(f"Extracted {len(active_ingredients)} active and {len(inactive_ingredients)} inactive ingredients")
    return active_ingredients, inactive_ingredients


def clean_ingredient_name(ingredient: str) -> str:
    """
    Clean up an ingredient name by removing UNII codes and standardizing whitespace.
    
    Args:
        ingredient: Raw ingredient string
        
    Returns:
        Cleaned ingredient name
    """
    # Clean up UNII codes
    if '(UNII:' in ingredient:
        ingredient = ingredient.split('(UNII:')[0].strip()
    
    # Clean up special characters and excessive whitespace
    ingredient = re.sub(r'\s+', ' ', ingredient).strip()  # Replace multiple spaces with a single space
    ingredient = re.sub(r'\t+', ' ', ingredient).strip()  # Replace tabs with a single space
    ingredient = re.sub(r'\n+', ' ', ingredient).strip()  # Replace newlines with a single space
    
    return ingredient.strip()


def extract_ingredients_from_text(text: str, active_ingredients: List[str], inactive_ingredients: List[str]) -> None:
    """
    Extract ingredient mentions from text content.
    
    Args:
        text: Text to search for ingredient mentions
        active_ingredients: List to append active ingredients to
        inactive_ingredients: List to append inactive ingredients to
    """
    # Check for active ingredients
    if 'active ingredient' in text:
        # Try to extract after colon or pattern like "Active Ingredient(s): X, Y, Z"
        if ':' in text:
            text_parts = text.split(':', 1)
            if len(text_parts) > 1 and 'active ingredient' in text_parts[0]:
                active_text = text_parts[1].strip()
                # Split by common separators
                for separator in [',', ';', '•', '\n']:
                    if separator in active_text:
                        ingredients = [i.strip() for i in active_text.split(separator)]
                        for ingredient in ingredients:
                            if ingredient and len(ingredient) > 2:
                                active_ingredients.append(ingredient)
                        break
                else:
                    # No separators found, use the whole text
                    if active_text and len(active_text) > 2:
                        active_ingredients.append(active_text)
    
    # Check for inactive ingredients
    if 'inactive ingredient' in text:
        # Try to extract after colon
        if ':' in text:
            text_parts = text.split(':', 1)
            if len(text_parts) > 1 and 'inactive ingredient' in text_parts[0]:
                inactive_text = text_parts[1].strip()
                # Split by common separators
                for separator in [',', ';', '•', '\n']:
                    if separator in inactive_text:
                        ingredients = [i.strip() for i in inactive_text.split(separator)]
                        for ingredient in ingredients:
                            if ingredient and len(ingredient) > 2:
                                inactive_ingredients.append(ingredient)
                        break
                else:
                    # No separators found, use the whole text
                    if inactive_text and len(inactive_text) > 2:
                        inactive_ingredients.append(inactive_text)


def deduplicate_and_clean_ingredients(ingredients: List[str]) -> List[str]:
    """
    Clean up and deduplicate a list of ingredients.
    
    Args:
        ingredients: List of ingredient strings
        
    Returns:
        Deduplicated and cleaned list
    """
    # Common terms that are NOT ingredients but often appear in ingredient sections
    non_ingredient_terms = [
        'product', 'information', 'type', 'route', 'administration',
        'inactive ingredient', 'characteristic', 'color', 'score', 'shape', 'flavor',
        'imprint', 'contains', 'packaging', 'marketing', 'code', 'anda', 'ndc',
        'labeler', 'establishment', 'size', 'source', 'oral', 'moiety', 'strength',
        'drug', 'prescription', 'tablet',
        'basis', 'name', 'round', 'human'
    ]
    
    # Filter and clean ingredients
    filtered_ingredients = []
    seen_lower = set()  # Track ingredients in lowercase for case-insensitive deduplication
    
    for ingredient in ingredients:
        # Skip entries that are too short
        if len(ingredient) < 3:
            continue
        
        # Skip entries that contain too many words (likely not an ingredient)
        if len(ingredient.split()) > 6:
            continue
        
        # Skip entries that have non-ingredient terms
        if any(term.lower() in ingredient.lower() for term in non_ingredient_terms):
            # But allow if the ingredient actually contains a real chemical name
            chemical_indicators = ['oxide', 'stearate', 'calcium', 'phosphate', 'dioxide', 
                                 'mannitol', 'starch', 'silicon', 'sodium', 'magnesium']
            if not any(chem in ingredient.lower() for chem in chemical_indicators):
                continue
        
        # Clean the ingredient name one more time
        ingredient = clean_ingredient_name(ingredient)
        
        # Check for duplicates case-insensitively
        if ingredient.lower() not in seen_lower:
            seen_lower.add(ingredient.lower())
            filtered_ingredients.append(ingredient)
    
    return filtered_ingredients


def extract_tables(soup: BeautifulSoup) -> Dict[str, List[List[Dict[str, str]]]]:
    """
    Extract tables from DailyMed HTML organized by section.
    
    Args:
        soup: BeautifulSoup object of the drug page
        
    Returns:
        Dictionary mapping section headings to lists of tables,
        where each table is a list of row dicts {column_header: cell_value}
    """
    tables_by_section = {}
    
    try:
        # Find all tables
        all_tables = soup.find_all('table')
        logger.debug(f"Found {len(all_tables)} tables in document")
        
        # Process each table
        for table in all_tables:
            # Find the section this table belongs to
            section_heading = None
            parent = table.parent
            
            # Look up the DOM tree to find a section heading
            while parent and parent.name != 'body':
                heading = parent.find(['h1', 'h2', 'h3'], recursive=False)
                if heading:
                    section_heading = heading.get_text(strip=True)
                    break
                parent = parent.parent
            
            # If no section heading found, try to find the closest preceding heading
            if not section_heading:
                previous_headings = []
                previous_element = table.find_previous(['h1', 'h2', 'h3'])
                if previous_element:
                    section_heading = previous_element.get_text(strip=True)
                else:
                    section_heading = "Unnamed Section"
            
            # Process the table data
            processed_table = []
            # Enhanced header-detection for multi-row headers
            rows = table.find_all('tr')
            headers = []
            data_start_idx = 1
            if rows:
                first_row_cells = rows[0].find_all(['th', 'td'])
                if (
                    len(first_row_cells) == 1 and
                    first_row_cells[0].has_attr('colspan') and
                    int(first_row_cells[0]['colspan']) > 1 and
                    len(rows) > 1
                ):
                    # First row is a spanning title, use second row as header
                    header_row = rows[1]
                    data_start_idx = 2
                else:
                    header_row = rows[0]
                    data_start_idx = 1
                headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
            # If no headers found, use column indices
            if not headers:
                # Find the row with the most cells to estimate columns
                max_cells = 0
                for row in rows:
                    cells = len(row.find_all(['td', 'th']))
                    max_cells = max(max_cells, cells)
                headers = [f"Column {i+1}" for i in range(max_cells)]
            # Process data rows
            for row in rows[data_start_idx:]:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_data = {}
                    for idx, cell in enumerate(cells):
                        if idx < len(headers):
                            header = headers[idx]
                            row_data[header] = cell.get_text(strip=True)
                        else:
                            # Handle case where there are more cells than headers
                            row_data[f"Column {idx+1}"] = cell.get_text(strip=True)
                    processed_table.append(row_data)
            # Add to section tables
            if processed_table:
                if section_heading not in tables_by_section:
                    tables_by_section[section_heading] = []
                tables_by_section[section_heading].append(processed_table)
    except Exception as e:
        logger.error(f"Error extracting tables: {str(e)}")
    
    logger.debug(f"Extracted tables from {len(tables_by_section)} sections")
    return tables_by_section

def _extract_toc_sections(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Parse the Full Prescribing Information TOC list items and their content divs.
    Returns a map of section titles to their text.
    """
    toc_sections = {}
    # Find any list item whose anchor id starts with "anch_dj_"
    for li in soup.find_all('li'):
        a = li.find('a', id=re.compile(r'^anch_dj_'))
        if not a:
            continue
        # Extract title and normalize
        title = a.get_text(strip=True).upper()
        # Remove leading numbering
        title = re.sub(r'^\d+\s+', '', title)
        if title not in IMPORTANT_CLINICAL_SECTIONS:
            continue
        # Find the associated content div (has class containing "Section")
        content_div = li.find('div', class_=lambda c: c and 'Section' in c)
        if content_div:
            toc_sections[title] = content_div.get_text(separator='\n', strip=True)
    return toc_sections

def extract_clinical_sections_from_xml(set_id: str) -> Dict[str, str]:
    """
    Fetch the SPL XML for set_id and parse out the important clinical sections.
    """
    url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{set_id}.xml"
    resp = requests.get(url)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    sections = {}
    for section in root.findall(".//section"):
        # Look for the section title
        title_elem = section.find("title")
        if title_elem is None:
            continue
        title_text = title_elem.text.strip().upper()
        if title_text in IMPORTANT_CLINICAL_SECTIONS:
            # find <text> child; fallback to all text under section
            text_elem = section.find("text")
            if text_elem is not None:
                text = "".join(text_elem.itertext()).strip()
            else:
                text = "".join(section.itertext()).strip()
            sections[title_text] = text
    return sections

# New: Extract clinical sections from the DailyMed JSON API
def extract_clinical_sections_from_api(set_id: str) -> Dict[str, str]:
    """
    Fetch the SPL JSON for set_id and parse out the important clinical sections.
    """
    url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{set_id}.json"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    sections = {}
    # JSON structure: data['spl']['splSections'] is a list of section dicts
    for sec in data.get('spl', {}).get('splSections', []):
        title = sec.get('sectionName', '').strip().upper()
        if title in IMPORTANT_CLINICAL_SECTIONS:
            # sectionText may contain HTML or plain text
            content = sec.get('sectionText', '').strip()
            sections[title] = content
    return sections


def extract_clinical_sections(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract important clinical sections from DailyMed SPL HTML fallback via TOC anchors.
    Returns a dict mapping section titles (from IMPORTANT_CLINICAL_SECTIONS) to their content.
    """
    # Use the Table of Contents anchors for full prescribing information sections
    sections = _extract_toc_sections(soup)
    # Warn if any expected sections are missing
    missing = [sec for sec in IMPORTANT_CLINICAL_SECTIONS if sec not in sections]
    if missing:
        logger.warning(f"Missing clinical sections in HTML fallback: {missing}")

    # XML fallback for missing sections
    # Try to get set_id from soup using extract_basic_info
    try:
        basic_info = extract_basic_info(soup)
    except Exception as e:
        logger.warning(f"Error extracting basic info for XML fallback: {e}")
        basic_info = {}
    if not sections or any(sec not in sections for sec in IMPORTANT_CLINICAL_SECTIONS):
        try:
            set_id = basic_info.get('set_id') or basic_info.get('setid') or ""
            xml_secs = extract_clinical_sections_from_xml(set_id)
            # Merge in any XML-provided sections that HTML missed
            for title, content in xml_secs.items():
                if title not in sections or not sections.get(title):
                    sections[title] = content
        except Exception as e:
            logger.warning(f"XML fallback failed: {e}")
    return sections

# Unified assembly helper
def assemble_drug_record(soup: BeautifulSoup, url: str = "", setid: str = "") -> Dict[str, Any]:
    """
    Build a unified drug record dict from the parsed HTML soup.
    """
    # Always extract basic info first
    basic = extract_basic_info(soup)
    api_setid = setid or basic.get("set_id")

    # API-aware clinical section merge
    if api_setid:
        try:
            api_secs = extract_clinical_sections_from_api(api_setid)
        except Exception:
            api_secs = {}
        html_secs = extract_clinical_sections(soup)
        # Prefer HTML content when both exist
        clinical_sections = {**api_secs, **html_secs}
    else:
        clinical_sections = extract_clinical_sections(soup)

    # General sections and content
    sections = extract_full_sections(soup)
    # Tables grouped by section
    tables = extract_tables(soup)
    # Ingredients
    active, inactive = extract_ingredients(soup)

    return {
        "metadata": {
            "set_id": api_setid,
            "drug_name": basic.get("title"),
            "manufacturer": basic.get("manufacturer"),
            "drug_class": basic.get("drug_class"),
            "ndc_codes": basic.get("ndc_codes"),
            "url": url
        },
        "downloads": basic.get("downloads", {}),
        "ingredients": {
            "active": active,
            "inactive": inactive
        },
        "clinical_sections": clinical_sections,  # Add dedicated clinical sections
        "sections": sections,
        "tables": tables
    }

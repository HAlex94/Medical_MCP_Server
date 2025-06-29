"""
DailyMed Parsing Module

Provides functions for parsing HTML content from DailyMed.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

from bs4 import BeautifulSoup, Tag

# Setup logging
logger = logging.getLogger(__name__)


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
            data['title'] = title_elem.get_text(strip=True)
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
                        # Extract text around the indicator
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
            # Clean up the text
            class_text = re.sub(r'\s+', ' ', class_text)
            data['drug_class'] = class_text
            logger.debug(f"Extracted drug class: {class_text}")
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
        # Extract NDC codes
        ndc_section = None
        ndc_codes = []
        
        # Look for NDC section
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            if 'ndc' in heading.get_text().lower():
                ndc_section = heading.find_next(['div', 'p', 'ul', 'table'])
                break
        
        if ndc_section:
            # Extract from tables
            tables = ndc_section.find_all('table')
            if tables:
                for table in tables:
                    for row in table.find_all('tr'):
                        cells = row.find_all(['td', 'th'])
                        for cell in cells:
                            # Look for NDC pattern (e.g., 12345-678-90)
                            ndc_matches = re.findall(r'\b\d{4,5}-\d{3,4}-\d{1,2}\b', cell.get_text())
                            ndc_codes.extend(ndc_matches)
            
            # Extract from text
            if not ndc_codes:
                text = ndc_section.get_text(strip=True)
                ndc_codes = re.findall(r'\b\d{4,5}-\d{3,4}-\d{1,2}\b', text)
        
        if ndc_codes:
            data['ndc_codes'] = ndc_codes
            logger.debug(f"Extracted {len(ndc_codes)} NDC codes")
    except Exception as e:
        logger.error(f"Error extracting NDC codes: {str(e)}")
    
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
    
    try:
        # Find all main section divs - multiple approaches
        section_divs = soup.select('.Section')
        
        # If that fails, try alternate selectors
        if not section_divs:
            section_divs = soup.select('.section')
        
        if not section_divs:
            # Try to find sections by looking for common patterns
            section_divs = []
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                if heading.get_text(strip=True):
                    # Find the content that follows this heading
                    next_siblings = []
                    current = heading.find_next_sibling()
                    
                    # Collect siblings until the next heading
                    while current and current.name not in ['h1', 'h2', 'h3']:
                        next_siblings.append(current)
                        current = current.find_next_sibling()
                    
                    if next_siblings:
                        # Create a container div
                        section_div = soup.new_tag('div')
                        section_div.append(heading)
                        for sibling in next_siblings:
                            section_div.append(sibling)
                        section_divs.append(section_div)
        
        # Process each section
        for section in section_divs:
            # Extract heading
            heading_elem = section.find(['h1', 'h2', 'h3']) or section.find(class_=re.compile(r'heading|title', re.I))
            
            if heading_elem:
                heading = heading_elem.get_text(strip=True)
            else:
                # No heading found, use first few words of content
                content_text = section.get_text(strip=True)
                heading = content_text[:30] + "..." if len(content_text) > 30 else content_text
            
            # Extract content - exclude the heading
            content = ""
            for element in section.find_all(['p', 'div', 'span', 'ul', 'ol', 'table']):
                if not element.find_parent(['table']):  # Avoid duplicate content from tables
                    text = element.get_text(strip=True)
                    if text:
                        content += text + "\n\n"
            
            if heading and content:
                sections[heading] = content.strip()
    except Exception as e:
        logger.error(f"Error extracting sections: {str(e)}")
    
    # If no sections found using the main approach, try a generic approach
    if not sections:
        try:
            # Look for any content div with reasonable structure
            content_div = soup.select_one('#content') or soup.select_one('.content') or soup.select_one('main')
            
            if content_div:
                # Find all headings and associate with following content
                current_heading = None
                current_content = []
                
                for element in content_div.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div', 'span', 'ul', 'ol']):
                    # Check if this is a heading
                    if element.name in ['h1', 'h2', 'h3', 'h4']:
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
    
    logger.debug(f"Extracted {len(sections)} sections")
    return sections


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
            
            # Get headers first
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # If no headers found, use column indices
            if not headers:
                # Find the row with the most cells to estimate columns
                max_cells = 0
                for row in table.find_all('tr'):
                    cells = len(row.find_all(['td', 'th']))
                    max_cells = max(max_cells, cells)
                
                headers = [f"Column {i+1}" for i in range(max_cells)]
            
            # Process data rows
            for row in table.find_all('tr')[1:]:  # Skip header row
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

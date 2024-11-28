import requests
from lxml import html
import logging
import schedule
import time
import sqlite3
import json
import csv
import os
import argparse
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO)

def init_db(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # Table to store fetched data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seo_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            element TEXT,
            data TEXT
        )
    ''')
    # Table to store differences between fetched data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS differences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            element TEXT,
            data TEXT,
            difference TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logging.info(f"Initialized DB : {os.path.abspath(db_name)}")

def is_allowed_by_robots(url, user_agent='*'):
    """Check if the URL is allowed to be crawled according to robots.txt"""
    try:
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        logging.error(f"Error checking robots.txt for {url}: {e}")
        return True  # Be permissive if robots.txt cannot be fetched

def find_xpath_link(source_url, target_url):
    """Find the XPath of the link from source_url to target_url, handling relative URLs and <base> tags"""
    if not source_url or not target_url:
        return None, None, None, None, None, None, None
    try:
        response = requests.get(source_url, timeout=10)
        tree = html.fromstring(response.content)

        # Get base URL from <base> tag if present
        base_url = tree.xpath("//base/@href")
        if base_url:
            base_url = base_url[0]
        else:
            base_url = source_url

        # Get all <a> elements
        links = tree.xpath("//a[@href]")
        target_url_parsed = urlparse(target_url)
        if not target_url_parsed.scheme:
            target_url = urljoin(base_url, target_url)

        # Initialize variables
        link_found = None
        xpath = None
        hrefs_resolved = []
        anchor_text = None
        parent_text = None
        rel_attribute = None

        for link in links:
            href = link.get('href')
            # Skip fragments
            href = href.split('#')[0]
            full_href = urljoin(base_url, href)
            hrefs_resolved.append(full_href)
            if full_href == target_url:
                link_found = link
                xpath = link.getroottree().getpath(link)
                rel_attribute = link.get('rel')
                anchor_text = link.text_content().strip()
                parent_text = link.getparent().text_content().strip()
                break

        # Extract the 'robots' attribute from the meta tag
        robots_meta = tree.xpath("//meta[@name='robots']/@content")
        robots_content = robots_meta[0] if robots_meta else None

        # Get x-robots-tag from HTTP headers
        x_robots_tag = response.headers.get('X-Robots-Tag')

        return xpath, hrefs_resolved, rel_attribute, robots_content, x_robots_tag, anchor_text, parent_text
    except Exception as e:
        logging.error(f"Error fetching {source_url}: {e}")
        return None, None, None, None, None, None, None

def check_basics_elements(url):
    """Check basic SEO elements on the page, including titles, descriptions, headings, robots directives, and x-robots-tag"""
    if not url:
        return [], [], {}, [], None, None, None
    try:
        if not is_allowed_by_robots(url):
            logging.warning(f"URL {url} is disallowed by robots.txt")
            is_allowed = False
            # return [], [], {}, [], None, None, False
        else:
            is_allowed = True
        response = requests.get(url, timeout=10)
        tree = html.fromstring(response.content)
        titles = tree.xpath("//title")
        content_title_list = [title.text.strip() for title in titles if title.text]
        content_description_list = tree.xpath("//meta[@name='description']/@content")
        heading_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        counts = {tag: 0 for tag in heading_tags}
        contents_h_tags = []
        for element in tree.iter():
            if element.tag in heading_tags:
                counts[element.tag] += 1
                text = element.text_content().strip()
                contents_h_tags.append((element.tag, text))
        # Extract the 'robots' attribute from the meta tag
        robots_meta = tree.xpath("//meta[@name='robots']/@content")
        robots_content = robots_meta[0] if robots_meta else None
        # Get x-robots-tag from HTTP headers
        x_robots_tag = response.headers.get('X-Robots-Tag')
        """is_allowed = True  # Since we have already checked robots.txt"""
        return content_title_list, content_description_list, counts, contents_h_tags, robots_content, x_robots_tag, is_allowed
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return [], [], {}, [], None, None, None

def analyze_changes(prev_entry, last_entry, db_name='seo_data.db'):
    """Analyze changes between previous and last entries and store differences in the database"""
    columns = ['id', 'timestamp', 'type', 'element', 'data']
    prev_data = dict(zip(columns, prev_entry))
    last_data = dict(zip(columns, last_entry))
    differences = []
    # Load JSON data
    prev_data_content = json.loads(prev_data['data'])
    last_data_content = json.loads(last_data['data'])
    # Comparing data based on type
    if prev_data['type'] == 'link':
        # Comparing various attributes
        for key in ['link_xpath', 'links_list', 'rel_attribute', 'robots_content', 'x_robots_tag', 'anchor_text', 'parent_text', 'is_allowed_by_robots']:
            if prev_data_content.get(key) != last_data_content.get(key):
                differences.append(f"{key} changed from {prev_data_content.get(key)} to {last_data_content.get(key)}")
    elif prev_data['type'] == 'url':
        # Comparing various attributes
        for key in ['titles', 'descriptions', 'htags_counts', 'htags_contents', 'robots_content', 'x_robots_tag', 'is_allowed_by_robots']:
            if prev_data_content.get(key) != last_data_content.get(key):
                differences.append(f"{key} changed from {prev_data_content.get(key)} to {last_data_content.get(key)}")
    # Storing differences in the database
    if differences:
        logging.info("Changes detected:")
        for diff in differences:
            logging.info(diff)
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        difference_text = '; '.join(differences)
        cursor.execute('''
            INSERT INTO differences (
                type,
                element,
                data,
                difference
            ) VALUES (?, ?, ?, ?)
        ''', (
            last_data['type'],
            last_data['element'],
            last_data['data'],
            difference_text
        ))
        conn.commit()
        conn.close()
    else:
        logging.info("No changes detected.")

def launch_functions(url_source, target_url, url_page, db_name='seo_data.db'):
    """Launch functions to check links and pages, store data, and analyze changes"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # Check and store links
    if url_source and target_url:
        type_entry = 'link'
        element = json.dumps([url_source, target_url])
        xpath, links_list, rel_attribute, robots_content, x_robots_tag, anchor_text, parent_text = find_xpath_link(url_source, target_url)
        data_content = {
            'link_xpath': xpath,
            'links_list': links_list,
            'rel_attribute': rel_attribute,
            'robots_content': robots_content,
            'x_robots_tag': x_robots_tag,
            'anchor_text': anchor_text,
            'parent_text': parent_text,
            'is_allowed_by_robots': is_allowed_by_robots(url_source)
        }
        data_json = json.dumps(data_content)
        # Storing data in the database
        cursor.execute('''
            INSERT INTO seo_data (
                type,
                element,
                data
            ) VALUES (?, ?, ?)
        ''', (
            type_entry,
            element,
            data_json
        ))
        conn.commit()
        # Check previous executions for this link
        cursor.execute('''
            SELECT COUNT(*) FROM seo_data
            WHERE type = ? AND element = ?
        ''', (type_entry, element))
        count = cursor.fetchone()[0]
        if count >= 2:
            cursor.execute('''
                SELECT * FROM seo_data
                WHERE type = ? AND element = ?
                ORDER BY id DESC LIMIT 2
            ''', (type_entry, element))
            last_two = cursor.fetchall()
            last_entry = last_two[0]
            prev_entry = last_two[1]
            analyze_changes(prev_entry, last_entry, db_name=db_name)
    # Check and store pages
    if url_page:
        type_entry = 'url'
        element = url_page
        titles, descriptions, counts, htags_contents, robots_content, x_robots_tag, is_allowed = check_basics_elements(url_page)
        data_content = {
            'titles': titles,
            'descriptions': descriptions,
            'htags_counts': counts,
            'htags_contents': htags_contents,
            'robots_content': robots_content,
            'x_robots_tag': x_robots_tag,
            'is_allowed_by_robots': is_allowed
        }
        data_json = json.dumps(data_content)
        cursor.execute('''
            INSERT INTO seo_data (
                type,
                element,
                data
            ) VALUES (?, ?, ?)
        ''', (
            type_entry,
            element,
            data_json
        ))
        conn.commit()
        # Check previous executions for this page
        cursor.execute('''
            SELECT COUNT(*) FROM seo_data
            WHERE type = ? AND element = ?
        ''', (type_entry, element))
        count = cursor.fetchone()[0]
        if count >= 2:
            cursor.execute('''
                SELECT * FROM seo_data
                WHERE type = ? AND element = ?
                ORDER BY id DESC LIMIT 2
            ''', (type_entry, element))
            last_two = cursor.fetchall()
            last_entry = last_two[0]
            prev_entry = last_two[1]
            analyze_changes(prev_entry, last_entry, db_name=db_name)
    conn.close()

def read_links_csv(csv_file, skip_lines=1):
    """Read links from a CSV file, skipping optional lines, validating URLs, and returning a list of tuples."""
    links = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip specified number of lines
            for _ in range(skip_lines):
                next(reader)
            for row in reader:
                # Ensure each field starts with 'http'
                if not len(row) >= 2:
                    raise Exception(f"Row in CSV file {csv_file} does not have at least two columns: {row}")
                source_url = row[0].strip()
                target_url = row[1].strip()
                if not source_url.startswith('http') or not target_url.startswith('http'):
                    raise Exception(f"Invalid URL in CSV file {csv_file}: {row}")
                links.append((source_url, target_url))
    except Exception as e:
        logging.error(f"Error reading CSV file {csv_file}: {e}")
    return links

def read_pages_txt(txt_file):
    """Read page URLs from a text file, ignoring headers"""
    pages = []
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            for line in f:
                page_url = line.strip()
                if page_url and not page_url.lower().startswith('url'):
                    pages.append(page_url)
    except Exception as e:
        logging.error(f"Error reading text file {txt_file}: {e}")
    return pages

def scheduled_task(links_list, pages_list, db_name='seo_data.db'):
    """Scheduled task to check links and pages, using parallel processing"""
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for url_source, target_url in links_list:
            futures.append(executor.submit(launch_functions, url_source, target_url, None, db_name))
        for url_page in pages_list:
            futures.append(executor.submit(launch_functions, None, None, url_page, db_name))
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error in scheduled task: {e}")

def main():
    parser = argparse.ArgumentParser(description='SEO Non-Regression Tests Script')
    parser.add_argument('--db', default='seo_data.db', help='Database name (default: seo_data.db)')
    parser.add_argument('--links-csv', help='Path to CSV file with source and target URLs')
    parser.add_argument('--pages-txt', help='Path to text file with URLs of pages to check')
    parser.add_argument('--frequency', type=int, default=1, help='Frequency of the task in minutes (default: 1 minute)')

    args = parser.parse_args()

    db_name = args.db
    init_db(db_name)

    links_list = read_links_csv(args.links_csv) if args.links_csv else []
    if not links_list and args.links_csv:
        logging.error("No valid link found in the CSV file.")

    pages_list = read_pages_txt(args.pages_txt) if args.pages_txt else []
    if not pages_list and args.pages_txt:
        logging.error("No valid page found in the text file.")

    if not links_list and not pages_list:
        logging.error("No links or pages to check. Exiting.")
        exit(1)

    schedule.every(args.frequency).minutes.do(scheduled_task, links_list=links_list, pages_list=pages_list, db_name=db_name)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()

import requests
from lxml import html
import logging
import schedule
import time
import sqlite3
import json
import csv
import os

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

def find_xpath_link(source_url, target_url):
    if not source_url or not target_url:
        return None, None, None, None
    try:
        response = requests.get(source_url, timeout=10)
        tree = html.fromstring(response.content)

        # Find all links with href equal to target_url
        links = tree.xpath(f"//a[@href='{target_url}']")

        # Extract the 'robots' attribute from the meta tag
        robots_meta = tree.xpath("//meta[@name='robots']/@content")
        robots_content = robots_meta[0] if robots_meta else None

        if links:
            link = links[0]
            links_list = tree.xpath(f"//a[@href='{target_url}']/@href")
            xpath = link.getroottree().getpath(link)
            # Check for the presence of the 'rel' attribute on the link tag
            rel_attribute = link.get('rel')
            return xpath, links_list, rel_attribute, robots_content
        else:
            return None, None, None, robots_content
    except Exception as e:
        logging.error(f"Error fetching {source_url}: {e}")
        return None, None, None, None


def check_basics_elements(url):
    if not url:
        return [], [], {}, []
    try:
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
        return content_title_list, content_description_list, counts, contents_h_tags
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return [], [], {}, []

def analyze_changes(prev_entry, last_entry, db_name='seo_data.db'):
    columns = ['id', 'timestamp', 'type', 'element', 'data']
    prev_data = dict(zip(columns, prev_entry))
    last_data = dict(zip(columns, last_entry))
    differences = []
    # Load JSON data
    prev_data_content = json.loads(prev_data['data'])
    last_data_content = json.loads(last_data['data'])
    # Comparing data based on type
    if prev_data['type'] == 'link':
        # Comparing link_xpath and links_list
        if prev_data_content.get('link_xpath') != last_data_content.get('link_xpath'):
            differences.append(f"link_xpath changed from {prev_data_content.get('link_xpath')} to {last_data_content.get('link_xpath')}")
        if prev_data_content.get('links_list') != last_data_content.get('links_list'):
            differences.append(f"links_list changed from {prev_data_content.get('links_list')} to {last_data_content.get('links_list')}")
        if prev_data_content.get('rel_attribute') != last_data_content.get('rel_attribute'):
            differences.append(f"rel_attribute changed from {prev_data_content.get('rel_attribute')} to {last_data_content.get('rel_attribute')}")
        if prev_data_content.get('robots_content') != last_data_content.get('robots_content'):
            differences.append(f"robots_content changed from {prev_data_content.get('robots_content')} to {last_data_content.get('robots_content')}")
    elif prev_data['type'] == 'url':
        # Comparing titles, descriptions, htags_counts and htags_contents
        if prev_data_content.get('titles') != last_data_content.get('titles'):
            differences.append(f"titles changed from {prev_data_content.get('titles')} to {last_data_content.get('titles')}")
        if prev_data_content.get('descriptions') != last_data_content.get('descriptions'):
            differences.append(f"descriptions changed from {prev_data_content.get('descriptions')} to {last_data_content.get('descriptions')}")
        if prev_data_content.get('htags_counts') != last_data_content.get('htags_counts'):
            differences.append(f"htags_counts changed from {prev_data_content.get('htags_counts')} to {last_data_content.get('htags_counts')}")
        if prev_data_content.get('htags_contents') != last_data_content.get('htags_contents'):
            differences.append("htags_contents changed")
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
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # Check and store links
    if url_source and target_url:
        type_entry = 'link'
        element = json.dumps([url_source, target_url])
        xpath, links_list, rel_attribute, robots_content = find_xpath_link(url_source, target_url)
        data_content = {
            'link_xpath': xpath,
            'links_list': links_list,
            'rel_attribute': rel_attribute,
            'robots_content': robots_content
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
        titles, descriptions, counts, htags_contents = check_basics_elements(url_page)
        data_content = {
            'titles': titles,
            'descriptions': descriptions,
            'htags_counts': counts,
            'htags_contents': htags_contents
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

def read_links_csv(csv_file):
    links = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            # Validating headers
            if 'source' in headers and 'target' in headers:
                reader = csv.DictReader(f, fieldnames=headers)
                for row in reader:
                    source_url = row['source'].strip()
                    target_url = row['target'].strip()
                    if source_url or target_url:
                        links.append((source_url, target_url))
            else:
                # Resetting the file pointer to read the file again
                f.seek(0)
                reader = csv.reader(f)
                for row in reader:
                    source_url = row[0].strip() if len(row) >= 1 else ''
                    target_url = row[1].strip() if len(row) >= 2 else ''
                    if source_url or target_url:
                        # Validating headers
                        if source_url.lower() != 'source' and target_url.lower() != 'target':
                            links.append((source_url, target_url))
    except Exception as e:
        logging.error(f"Error reading CSV file {csv_file}: {e}")
    return links

def read_pages_txt(txt_file):
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
    # link and page checking
    for url_source, target_url in links_list:
        launch_functions(url_source, target_url, None, db_name=db_name)
    for url_page in pages_list:
        launch_functions(None, None, url_page, db_name=db_name)

if __name__ == '__main__':
    db_name = 'seo_data.db'
    init_db(db_name)
    # Ask the user if they want to provide a CSV file with links to check
    use_links = input("Do you want to provide a CSV file with source and target URLs? (y/n) : ").lower()
    if use_links == 'y':
        csv_file = input("Enter the path to the CSV file with source and target URLs: ")
        links_list = read_links_csv(csv_file)
        if not links_list:
            logging.error("No valid link found in the CSV file.")
            links_list = []
    else:
        links_list = []
    # Ask the user if they want to provide a text file with pages to check
    use_pages = input("Do you want to provide a text file with URLs of pages to check? (y/n) : ").lower()
    if use_pages == 'y':
        txt_file = input("Enter the path to the text file with URLs of pages to check: ")
        pages_list = read_pages_txt(txt_file)
        if not pages_list:
            logging.error("No valid page found in the text file.")
            pages_list = []
    else:
        pages_list = []
    # Check if there are links or pages to check
    if not links_list and not pages_list:
        logging.error("No links or pages to check. Exiting.")
        exit(1)
    # Schedule the task to run
    frequency = input("Enter the frequency of the task in minutes (default is 1 minute): ")
    if not frequency.isdigit():
        frequency = 1
    else:
        frequency = int(frequency)
    schedule.every(frequency).minutes.do(scheduled_task, links_list=links_list, pages_list=pages_list, db_name=db_name)
    while True:
        schedule.run_pending()
        time.sleep(1)

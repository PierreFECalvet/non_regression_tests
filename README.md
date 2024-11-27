# SEO Non-Regression Testing Script

This script performs non-regression tests on SEO elements of websites. It checks for changes in links and page content over time, comparing each execution to the previous one for the same element. The script stores data in a SQLite database and logs any differences detected between runs.

## Features

- **Link Verification:**
  - Checks the presence of specific links on source pages.
  - Verifies the XPath location of links.
  - Checks for the presence or absence of the `rel` attribute on link tags.
  - Extracts the `robots` meta tag content from the source page.

- **Page Content Verification:**
  - Checks page titles and meta descriptions.
  - Counts heading tags (`<h1>` to `<h6>`) and their content.

- **Data Storage and Analysis:**
  - Stores data in a SQLite database (`seo_data.db`).
  - Compares current data with previous runs for the same element.
  - Logs differences in a `differences` table.
  - Exports differences and data to CSV files.

## Requirements

- Python 3.x
- The packages listed in `requirements.txt`.

## Installation

1. **Clone the Repository:**
```bash
   git clone https://github.com/PierreFECalvet/non_regression_tests.git
   cd non_regression_tests
```

2. **Install Dependencies:**

    Install the required Python packages using pip:
```bash
    pip install -r requirements.txt
```

## Usage

1. **Running the Main Script**
Execute the main script to start the non-regression testing:

```bash
python basics_seo_non_regression_tests.py
```
2. **User Prompts**
The script will prompt you for:

- **Links to Check:**
    Whether you want to provide a CSV file with source and target URLs.
    The path to the CSV file if applicable.

- **Pages to Check:**
    Whether you want to provide a text file with URLs of pages to check.
    The path to the text file if applicable.

- **Frequency:**
    The frequency in minutes at which the script should run.

- **Input File Formats**
    CSV File for Links (links.csv):
    The CSV file should contain the columns source and target. For example:

```
    source,target
    http://example.com, http://example.com/target-page
    http://anotherdomain.com, http://anotherdomain.com/target-page
```

Text File for Pages (pages.txt):
Each line should contain a single URL to a page to check. For example:

```
    http://example.com/page1
    http://example.com/page2
```

3. **Exporting Data**
A separate script export_data.py is provided to export data from the database to CSV files.

Run the script:
```bash
    python export_data.py
```

You will be prompted to choose whether to export differences and/or SEO data, and whether to clear the tables after exporting.

4. **Database Structure**
**seo_data Table:**
- id: Unique identifier.
- timestamp: Date and time of data capture.
- type: Either url (for pages) or link.
- element: URL of the page or JSON array of [source_url, target_url].
- data: JSON-formatted data specific to the element.

**differences Table:**
- Same structure as seo_data, with an additional difference field describing detected changes.

**Notes**
- Ensure Valid URLs: Make sure that the URLs provided are valid and accessible to avoid errors during HTTP requests.
- Database File Location: The script creates a seo_data.db SQLite database file in the script's directory. Ensure you have write permissions in this directory.
- Scheduling Interval: You can adjust the frequency of the task when prompted. The default is every 1 minute.
- Concurrent Execution: If you have many URLs to check, consider increasing the interval to prevent overloading the target servers.

**Troubleshooting**
    **Common Errors:**
- TypeError: unsupported type for timedelta minutes component: str: Ensure that the frequency input is a valid integer.
- sqlite3.OperationalError: no such table: seo_data: Make sure the database is initialized before running the script.
- Logging: 
The script uses Python's logging module to output information. Check the console output for logs about the scraping process and any detected changes.

**License**
    This project is licensed under the MIT License - see the LICENSE file for details.

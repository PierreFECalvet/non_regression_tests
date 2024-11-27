import sqlite3
import csv
import os

def export_differences_to_csv(db_name='seo_data.db', csv_filename='differences.csv'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM differences')
    rows = cursor.fetchall()
    if rows:
        # Get column names
        column_names = [description[0] for description in cursor.description]
        # Write to the CSV file
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(column_names)
            csv_writer.writerows(rows)
        print(f"Differences have been exported to {csv_filename}.")
    else:
        print("No differences to export.")
    conn.close()

def export_seo_data_to_csv(db_name='seo_data.db', csv_filename='seo_data.csv'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM seo_data')
    rows = cursor.fetchall()
    if rows:
        # Obtenir les noms des colonnes
        column_names = [description[0] for description in cursor.description]
        # Écrire dans le fichier CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(column_names)
            csv_writer.writerows(rows)
        print(f"SEO data has been exported to {csv_filename}.")
    else:
        print("No SEO data to export.")
    conn.close()

def clear_differences_table(db_name='seo_data.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM differences')
    conn.commit()
    conn.close()
    print("The 'differences' table has been cleared.")

def keep_last_seo_data_entries(db_name='seo_data.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # Delete all entries except the last one for each unique combination of type and element
    cursor.execute('''
        DELETE FROM seo_data
        WHERE id NOT IN (
            SELECT MAX(id) FROM seo_data GROUP BY type, element
        )
    ''')
    conn.commit()
    conn.close()
    print("The 'seo_data' table has been cleaned to keep only the last entry for each element.")

if __name__ == '__main__':
    db_name = 'seo_data.db'

    execute_differences = input("Do you want to export the differences? (y/n) : ").lower()
    execute_seo_data = input("Do you want to export the SEO data? (y/n) : ").lower()

    if execute_differences == 'y':
        export_differences_to_csv(db_name=db_name)
        clear_diff = input("Do you want to clear the 'differences' table after export? (y/n) : ").lower()
        if clear_diff == 'y':
            clear_differences_table(db_name=db_name)

    if execute_seo_data == 'y':
        export_seo_data_to_csv(db_name=db_name)
        clear_seo = input("Do you want to clean the 'seo_data' table after export (keep only the last entry for each element)? (y/n) : ").lower()
        if clear_seo == 'y':
            keep_last_seo_data_entries(db_name=db_name)
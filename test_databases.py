import os
import sqlite3
import argparse
import time

def test_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        cursor.fetchall()
        conn.close()
        return "OK"
    except sqlite3.OperationalError as e:
        if "disk I/O error" in str(e):
            return "disk I/O error"
        else:
            return f"OperationalError: {e}"
    except sqlite3.DatabaseError as e:
        if "database disk image is malformed" in str(e):
            return "database disk image is malformed"
        else:
            return f"DatabaseError: {e}"

def test_database_with_retries(db_path, max_retries=5, max_directories=10):
    retries = 0
    base_path, db_name = os.path.split(db_path)  # Split into base path and db_name

    while retries < max_retries:
        status = test_database(db_path)
        if status == "OK":
            return status, retries + 1, base_path
        elif status in ["disk I/O error", "database disk image is malformed"]:
            retries += 1
            time.sleep(1)  # Adding a delay before retrying
            continue
        else:
            return status, retries + 1, base_path

    for i in range(2, max_directories + 1):
        new_base_path = f"{base_path}{i}"
        new_db_path = os.path.join(new_base_path, db_name)
        retries = 0
        while retries < max_retries:
            status = test_database(new_db_path)
            if status == "OK":
                return status, retries + 1, new_base_path
            elif status in ["disk I/O error", "database disk image is malformed"]:
                retries += 1
                time.sleep(1)  # Adding a delay before retrying
                continue
            else:
                return status, retries + 1, new_base_path

    return f"Failed after trying {max_directories} directories", retries + 1, new_base_path

def main(directory):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            db_id = dir_name
            db_file = os.path.join(root, dir_name, f"{db_id}.sqlite")
            if os.path.isfile(db_file):
                status, attempts, last_directory = test_database_with_retries(db_file)
                print(f"Database ID: {db_id}, Attempts: {attempts}, Last Directory: {last_directory}, Status: {status}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test SQLite databases in a directory.")
    parser.add_argument("directory", type=str, help="Path to the directory containing the database folders.")
    args = parser.parse_args()
    
    main(args.directory)

import os
import csv
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL")
DB_NAME = "ai_courtroom"
COLLECTION_NAME = "cases"

def count_cases_by_section():
    client = None
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URL)
        db = client[DB_NAME]
        cases_collection = db[COLLECTION_NAME]

        print("Connected to MongoDB. Counting cases by section...")

        # Aggregate to count cases by section
        pipeline_section = [
            {"$group": {"_id": "$section", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        section_counts = list(cases_collection.aggregate(pipeline_section))

        if not section_counts:
            print("No cases found in the collection.")
        else:
            # Define CSV file path for sections
            csv_file_path_sections = "case_counts_by_section.csv"

            # Write to CSV
            with open(csv_file_path_sections, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Section", "Count"])
                for item in section_counts:
                    section_name = item.get("_id", "Unknown")
                    count = item.get("count", 0)
                    writer.writerow([section_name, count])
            
            print(f"Successfully exported case counts by section to {csv_file_path_sections}")

        print("Counting cases by status...")

        # Aggregate to count cases by status
        pipeline_status = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]

        status_counts = list(cases_collection.aggregate(pipeline_status))

        if not status_counts:
            print("No cases found with status.")
        else:
            # Define CSV file path for status
            csv_file_path_status = "case_counts_by_status.csv"

            # Write to CSV
            with open(csv_file_path_status, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Status", "Count"])
                for item in status_counts:
                    status_name = item.get("_id", "Unknown")
                    count = item.get("count", 0)
                    writer.writerow([status_name, count])
            
            print(f"Successfully exported case counts by status to {csv_file_path_status}")

        print("Counting cases by section and status...")

        # Aggregate to count cases by section and status
        pipeline_section_status = [
            {"$group": {"_id": {"section": "$section", "status": "$status"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]

        section_status_counts = list(cases_collection.aggregate(pipeline_section_status))

        if not section_status_counts:
            print("No cases found with section and status.")
        else:
            # Define CSV file path for section and status
            csv_file_path_section_status = "case_counts_by_section_and_status.csv"

            # Write to CSV
            with open(csv_file_path_section_status, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Section", "Status", "Count"])
                for item in section_status_counts:
                    section_name = item.get("_id", {}).get("section", "Unknown")
                    status_name = item.get("_id", {}).get("status", "Unknown")
                    count = item.get("count", 0)
                    writer.writerow([section_name, status_name, count])
            
            print(f"Successfully exported case counts by section and status to {csv_file_path_section_status}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client:
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    count_cases_by_section()
import asyncio
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from case_generation import generate_case

async def main():
    section_number = 499
    print(f"Generating a single case for section {section_number}...")
    try:
        case = await generate_case(sections=1, numbers=[section_number])
        if case:
            print("Case generated successfully:")
            print(json.dumps(case, indent=2))
            
            # Load environment variables
            load_dotenv()
            MONGODB_URL = os.getenv("MONGODB_URL")
            DB_NAME = "ai_courtroom"
            COLLECTION_NAME = "cases"

            client = MongoClient(MONGODB_URL)
            db = client[DB_NAME]
            cases_collection = db[COLLECTION_NAME]

            # Insert the case into MongoDB
            result = cases_collection.insert_one(case)
            case["_id"] = result.inserted_id
            print(f"Case saved to MongoDB with ID: {result.inserted_id}")

            # Optionally save to a file
            with open(f"case_section_{section_number}.json", "w", encoding="utf-8") as f:
                json.dump(case, f, indent=2, default=str) # Use default=str for ObjectId serialization
            print(f"Case saved to case_section_{section_number}.json")

            # Generate arguments for the case
            from pipeline import generate_arguments_for_case
            print(f"Generating arguments for case {case.get('title', 'Untitled')}...")
            await generate_arguments_for_case(case)
            print("Arguments generation complete.")

            client.close()
        else:
            print("Failed to generate case.")
    except Exception as e:
        print(f"An error occurred during case generation: {e}")

if __name__ == "__main__":
    asyncio.run(main())
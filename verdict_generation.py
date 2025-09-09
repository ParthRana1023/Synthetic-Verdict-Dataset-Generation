# verdict_generation.py
import asyncio
import os
import argparse
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from judge import generate_verdict
from llm_manager import get_all_models, set_current_model
import llm

# Load Environment Variables
load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL")
DB_NAME = "ai_courtroom"
CASES_COLLECTION_NAME = "cases"
VERDICTS_COLLECTION_NAME = "verdicts"

# Connect to MongoDB
client = MongoClient(MONGODB_URL)
db = client[DB_NAME]
cases_collection = db[CASES_COLLECTION_NAME]
verdicts_collection = db[VERDICTS_COLLECTION_NAME]

async def generate_and_save_verdict(case_id, model_name):
    """
    Generate a verdict for a specific case and save it to the verdicts collection.
    
    Args:
        case_id: The ObjectId of the case to generate a verdict for
        
    Returns:
        The generated verdict or None if case not found or error occurred
    """
    try:
        # Convert string ID to ObjectId if needed
        if isinstance(case_id, str):
            case_id = ObjectId(case_id)
            
        # Retrieve the case from MongoDB
        case = cases_collection.find_one({"_id": case_id})
        
        if not case:
            print(f"❌ Case with ID {case_id} not found")
            return None
            
        # Check if case is resolved (has all arguments)
        if case.get("status") != "resolved":
            print(f"⚠️ Case {case_id} is not resolved yet. Status: {case.get('status')}")
            return None
            
        # Extract required data for verdict generation
        plaintiff_args = case.get("plaintiff_arguments", [])
        defendant_args = case.get("defendant_arguments", [])
        case_details = case.get("details", "")
        section = case.get("section", "")
        case_title = case.get("title", "Untitled Case")
        
        print(f"🧑‍⚖️ Generating verdict for case: {case_title} (ID: {case_id})")
        
        # Generate the verdict
        llm_instance = llm.get_llm()
        verdict = await generate_verdict(
            plaintiff_args,
            defendant_args,
            case_details,
            case_title,
            llm_instance
        )
        
        if not verdict:
            print(f"❌ Failed to generate verdict for case {case_id}")
            return None
            
        # Save the verdict and complete case to the verdicts collection
        verdict_doc = {
            "_id": f"{str(case['_id'])}_{model_name.replace('/', '_')}",
            "case_ref": case['_id'],
            "case_title": case_title,
            "section": section,
            "case_details": case_details,
            "verdict": verdict,
            "model_name": model_name
        }
        
        result = verdicts_collection.insert_one(verdict_doc)
        print(f"✅ Saved verdict for case {case_title} (ID: {case_id}) to verdicts collection")

        return verdict
        
    except Exception as e:
        print(f"❌ Error generating verdict for case {case_id}: {str(e)}")
        return None

async def generate_verdicts_for_n_cases(n=None):
    """
    Generate verdicts for n resolved cases that don't already have verdicts.
    
    Args:
        n: Number of cases to generate verdicts for
        
    Returns:
        Number of verdicts successfully generated
    """
    # Find resolved cases that don't have verdicts yet
    # Find resolved cases that don't have verdicts yet
    cases_needing_verdicts = list(cases_collection.find({"status": "resolved"}))

    # Filter out cases that already have verdicts for all models
    all_models = get_all_models()
    cases_to_process = []
    for case in cases_needing_verdicts:
        case_id = str(case["_id"])
        existing_verdicts = verdicts_collection.find({"case_id": case_id}, {"model_name": 1})
        generated_models = {v.get("model_name") for v in existing_verdicts if v.get("model_name")}
        
        # Check if all models have generated a verdict for this case
        if not all(model in generated_models for model in all_models):
            cases_to_process.append(case)
    
    print(f"📊 Found {len(cases_needing_verdicts)} resolved cases without verdicts")
    
    # Limit to the requested number if n is provided
    if n is not None:
        cases_to_process = cases_to_process[:n]
    
    if not cases_to_process:
        print("ℹ️ No cases found that need verdicts")
        return 0
        
    print(f"🧑‍⚖️ Generating verdicts for {len(cases_to_process)} cases...")
    
    # Generate verdicts for each case
    successful_verdicts = 0
    for case in cases_to_process:
        case_id = case["_id"]
        for model_name in all_models:
            # Check if verdict already exists for this case and model
            verdict_doc_id = f"{case_id}_{model_name.replace('/', '_')}"
            if verdicts_collection.find_one({"_id": verdict_doc_id}):
                print(f"ℹ️ Verdict already exists for case {case_id} with model {model_name}. Skipping.")
                continue

            set_current_model(model_name)
            print(f"🔄 Generating verdict for case {case_id} using model: {model_name}")
            verdict = await generate_and_save_verdict(case_id, model_name)
            if verdict:
                successful_verdicts += 1

        # Update the original case with a flag indicating verdict generation
        cases_collection.update_one(
            {"_id": case_id},
            {"$set": {"verdict_generated": True}}
        )
        print(f"✅ Updated case {case_id} with verdict_generated flag")
            
    print(f"✅ Successfully generated {successful_verdicts} verdicts")
    return successful_verdicts

# Command-line interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate verdicts for cases.")
    parser.add_argument(
        "-n",
        "--num_cases",
        type=int,
        help="Number of cases to generate verdicts for. If not specified, all unprocessed cases will be evaluated."
    )
    args = parser.parse_args()

    try:
        asyncio.run(generate_verdicts_for_n_cases(args.num_cases))
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
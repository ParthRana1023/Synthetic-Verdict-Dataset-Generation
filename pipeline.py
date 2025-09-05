# pipeline.py
import asyncio
import time
import json
import os
from pymongo import MongoClient, errors
from bson import ObjectId
from dotenv import load_dotenv
from llm_manager import rotate_key, rotate_model, print_rotation_status
import json
from case_generation import generate_case
from lawyer import opening_statement, generate_counter_argument, closing_statement

# ---- Load Environment Variables ----
load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL")  # Cloud MongoDB URL from .env
DB_NAME = "ai_courtroom"
COLLECTION_NAME = "cases"

client = MongoClient(MONGODB_URL)
db = client[DB_NAME]
cases_collection = db[COLLECTION_NAME]

# Load IPC sections from JSON file
with open("top_80_ipc_sections.json", "r") as f:
    ipc_data = json.load(f)
    ipc_sections = [entry["Section"] for entry in ipc_data]

# ---- Rotation Status Tracking ----
def print_initial_rotation_status():
    """Print the initial rotation status at the beginning of the pipeline run."""
    print("\n📊 [INITIAL ROTATION STATUS]")
    stats = print_rotation_status()
    print("Starting pipeline with the above configuration...\n")
    return stats

def print_final_rotation_status(initial_stats):
    """Print the final rotation status at the end of the pipeline run."""
    print("\n📊 [FINAL ROTATION STATUS]")
    final_stats = print_rotation_status()
    
    # Calculate differences
    keys_used = initial_stats['keys_remaining'] - final_stats['keys_remaining']
    models_used = initial_stats['models_remaining'] - final_stats['models_remaining']
    rotation_count = final_stats['rotation_count']
    
    print(f"\n📈 [ROTATION SUMMARY]")
    print(f"   - Total rotations: {rotation_count}")
    print(f"   - API keys used: {keys_used} out of {initial_stats['total_keys']}")
    print(f"   - Models used: {models_used} out of {initial_stats['total_models']}")
    print(f"   - Starting model: {initial_stats['current_model']}")
    print(f"   - Ending model: {final_stats['current_model']}")
    
    # Print model-specific usage
    print(f"\n📊 [MODEL-SPECIFIC KEY USAGE]")
    for model, usage in final_stats['model_key_usage'].items():
        keys_used_for_model = usage['keys_used']
        total_keys_for_model = usage['total_keys']
        rotations_for_model = usage['rotations']
        print(f"   - {model}: {keys_used_for_model}/{total_keys_for_model} keys used ({rotations_for_model} rotations)")
    
    return final_stats

# ---- Retry Decorator ----
def retry_with_backoff(func):
    async def wrapper(*args, **kwargs):
        max_retries, delay = 5, 2  # Increased retries from 3 to 5
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_text = str(e)
                error_str = error_text.lower()

                # Try to parse JSON to check error type
                try:
                    error_json = json.loads(error_text.split("Error code:")[-1].strip())
                except Exception:
                    error_json = {}

                if "rate limit" in error_str:
                    # Check for daily token exhaustion
                    if "tokens per day" in error_str or error_json.get("error", {}).get("code") == "rate_limit_exceeded":
                        # For any TPD (tokens per day) error, always rotate model
                        print(f"⚠️ [DEBUG] Daily token limit reached. Rotating model... (Attempt {attempt+1}/{max_retries})")
                        print_rotation_status()  # Print current status before rotation
                        rotate_model()
                        await asyncio.sleep(20)  # Wait for 20 seconds after model rotation
                    else:
                        print(f"⚠️ [DEBUG] Short-term rate limit hit. Rotating key... (Attempt {attempt+1}/{max_retries})")
                        print_rotation_status()  # Print current status before rotation
                        rotate_key()
                        await asyncio.sleep(10)  # Wait for 10 seconds after key rotation
                    continue

                elif "503" in error_str or "over capacity" in error_str:
                    print(f"⚠️ [DEBUG] 503 error. Retrying in {delay}s (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(delay)
                    delay *= 2
                    
                    # If we've tried multiple times with backoff, try rotating
                    if attempt >= 2:
                        print(f"⚠️ [DEBUG] Multiple 503 errors. Trying key rotation...")
                        print_rotation_status()  # Print current status before rotation
                        rotate_key()

                else:
                    print(f"❌ [DEBUG] Other error: {e} (Attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        # For unknown errors, try rotating key first, then model if needed
                        print_rotation_status()  # Print current status before rotation
                        rotate_key()
                        await asyncio.sleep(5)
                        continue
                    
                # If we reach the last attempt and still have errors, raise the exception
                if attempt == max_retries - 1:
                    print(f"⛔ [DEBUG] All retry attempts failed. Raising exception.")
                    raise e
        
        # This should never be reached due to the exception above
        raise Exception("Maximum retries exceeded")
    return wrapper

def is_valid_response(text: str) -> bool:
    """Check if LLM output is a real argument, not a fallback message."""
    if not text:
        return False
    fallback_patterns = [
        "i apologize",
        "unable to",
        "please try again later",
        "failed after multiple retries"
    ]
    return not any(p in text.lower() for p in fallback_patterns)

def save_progress(case_id, plaintiff_args, defendant_args, status="in-progress"):
    """Incrementally update MongoDB with latest arguments."""
    try:
        cases_collection.update_one(
            {"_id": ObjectId(case_id)},
            {"$set": {
                "plaintiff_arguments": plaintiff_args,
                "defendant_arguments": defendant_args,
                "status": status
            }}
        )
        print(f"💾 Progress saved for case {case_id} (Status: {status})")
    except errors.PyMongoError as e:
        print(f"❌ MongoDB Update Error: {e}")

# ---- Generate / Complete Arguments for Case ----
@retry_with_backoff
async def generate_arguments_for_case(case: dict):
    case_details = case["details"]
    case_id = case["_id"]
    case_title = case.get("title", "Untitled")

    print(f"\n=== Working on case: {case_title} (ID: {case_id}) ===")

    # Resume if already has some arguments
    plaintiff_args = case.get("plaintiff_arguments", [])
    defendant_args = case.get("defendant_arguments", [])

    # Step 1: Opening Statements
    if len(plaintiff_args) == 0:
        print("🟢 Generating Plaintiff Opening...")
        resp = await opening_statement("Plaintiff", case_details, "Defendant")
        if resp and is_valid_response(resp):
            plaintiff_args.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print("⚠️ Failed to generate valid plaintiff opening statement. Will retry.")
            return False  # Signal retry needed

    if len(defendant_args) == 0:
        print("🟢 Generating Defendant Opening...")
        resp = await opening_statement("Defendant", case_details, "Plaintiff")
        if resp and is_valid_response(resp):
            defendant_args.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print("⚠️ Failed to generate valid defendant opening statement. Will retry.")
            return False  # Signal retry needed

    # Step 2: Arguments (2 rounds)
    history = plaintiff_args + defendant_args
    while len(plaintiff_args) < 3:  # opening + 2 args
        round_num = len(plaintiff_args)
        print(f"\n🔷 Plaintiff Argument {round_num}")
        arg_p = await generate_counter_argument(
            "\n".join(history),
            f"Plaintiff, present your round {round_num} argument",
            "Plaintiff",
            "Defendant",
            case_details
        )
        if arg_p and is_valid_response(arg_p):
            plaintiff_args.append(arg_p)
            history.append(arg_p)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print(f"⚠️ Failed to generate valid plaintiff argument {round_num}. Will retry.")
            return False  # Signal retry needed

        print(f"🔶 Defendant Counter {round_num}")
        arg_d = await generate_counter_argument(
            "\n".join(history),
            arg_p,
            "Defendant",
            "Plaintiff",
            case_details
        )
        if arg_d and is_valid_response(arg_d):
            defendant_args.append(arg_d)
            history.append(arg_d)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print(f"⚠️ Failed to generate valid defendant counter {round_num}. Will retry.")
            return False  # Signal retry needed

    # Step 3: Closings
    if len(plaintiff_args) < 4:
        print("\n🟢 Generating Plaintiff Closing...")
        resp = await closing_statement("\n".join(history), "Plaintiff", "Defendant")
        if resp and is_valid_response(resp):
            plaintiff_args.append(resp)
            history.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print("⚠️ Failed to generate valid plaintiff closing statement. Will retry.")
            return False  # Signal retry needed

    if len(defendant_args) < 4:
        print("🟢 Generating Defendant Closing...")
        resp = await closing_statement("\n".join(history), "Defendant", "Plaintiff")
        if resp and is_valid_response(resp):
            defendant_args.append(resp)
            history.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)
        else:
            print("⚠️ Failed to generate valid defendant closing statement. Will retry.")
            return False  # Signal retry needed

    # Step 4: Mark resolved only if both sides have 4 entries
    if len(plaintiff_args) == 4 and len(defendant_args) == 4:
        save_progress(case_id, plaintiff_args, defendant_args, status="resolved")
        print(f"✅ Case {case_id} marked RESOLVED.")
        return True  # Successfully completed
    else:
        print(f"⚠️ Case {case_id} incomplete. Will retry missing arguments next run.")
        return False  # Signal retry needed

# ---- Generate a New Case ----
@retry_with_backoff
async def run_single_case(section: int):
    print(f"\n📂 Creating new case for Section {section}...")
    case = await generate_case(1, [section])
    
    if not case:
        print(f"❌ Failed to generate case for Section {section}")
        raise ValueError("Failed to generate case")

    case_data = {
        "cnr": case["cnr"],
        "title": case["title"],
        "details": case["details"],
        "status": "details-only",
        "section": section
    }

    try:
        result = cases_collection.insert_one(case_data)
        case_data["_id"] = result.inserted_id
        print(f"✅ Inserted new case {case['title']} (CNR: {case['cnr']}) into MongoDB")
    except errors.PyMongoError as e:
        print(f"❌ MongoDB Insert Error: {e}")
        raise

    # Immediately generate arguments
    success = await generate_arguments_for_case(case_data)
    if not success:
        raise ValueError("Failed to generate arguments for case")
    return True  # Return success only if everything worked

# ---- Run for a Single Section ----
async def run_cases_for_section(section: int):
    # Process all cases in this order: details-only first, then in-progress, then generate new cases if needed
    existing_cases = list(cases_collection.find({"section": section}))
    details_only = [c for c in existing_cases if c.get("status") == "details-only"]
    in_progress = [c for c in existing_cases if c.get("status") == "in-progress"]
    resolved = [c for c in existing_cases if c.get("status") == "resolved"]

    print(f"\n📊 Section {section}: {len(resolved)} resolved, {len(details_only)} details-only, {len(in_progress)} in-progress cases in DB")

    did_work = False  # track if we generated anything
    max_retries_per_case = 2  # Maximum number of immediate retries per case

    # First, process all details-only cases (highest priority)
    print(f"\n🔍 Processing {len(details_only)} details-only cases for Section {section}...")
    for case in details_only:
        case_id = case.get('_id')
        success = False
        retries = 0
        
        while not success and retries < max_retries_per_case:
            try:
                print(f"{'🔄 Retrying' if retries > 0 else '🔍 Processing'} details-only case {case_id} (Attempt {retries+1}/{max_retries_per_case})")
                success = await generate_arguments_for_case(case)
                did_work = True
                
                if success:
                    print(f"✅ Successfully processed details-only case {case_id}")
                    break
                else:
                    print(f"⚠️ Case {case_id} needs another attempt")
                    retries += 1
                    # Wait a bit before retrying
                    await asyncio.sleep(5)
            except SystemExit:
                # If SystemExit is raised during processing an incomplete case,
                # it means we ran out of keys/models. Re-raise to terminate the pipeline.
                raise
            except Exception as e:
                print(f"❌ Error processing details-only case {case_id}: {e}")
                retries += 1
                await asyncio.sleep(5)
        
        if not success:
            print(f"⛔ Failed to process details-only case {case_id} after {max_retries_per_case} attempts")
    
    # Then, process all in-progress cases (second priority)
    print(f"\n🔍 Processing {len(in_progress)} in-progress cases for Section {section}...")
    for case in in_progress:
        case_id = case.get('_id')
        success = False
        retries = 0
        
        while not success and retries < max_retries_per_case:
            try:
                print(f"{'🔄 Retrying' if retries > 0 else '🔍 Processing'} in-progress case {case_id} (Attempt {retries+1}/{max_retries_per_case})")
                success = await generate_arguments_for_case(case)
                did_work = True
                
                if success:
                    print(f"✅ Successfully processed in-progress case {case_id}")
                    break
                else:
                    print(f"⚠️ Case {case_id} needs another attempt")
                    retries += 1
                    # Wait a bit before retrying
                    await asyncio.sleep(5)
            except SystemExit:
                # If SystemExit is raised during processing an incomplete case,
                # it means we ran out of keys/models. Re-raise to terminate the pipeline.
                raise
            except Exception as e:
                print(f"❌ Error processing in-progress case {case_id}: {e}")
                retries += 1
                await asyncio.sleep(5)
        
        if not success:
            print(f"⛔ Failed to process in-progress case {case_id} after {max_retries_per_case} attempts")

    # After attempting to complete incomplete cases, re-check their status
    resolved_count = cases_collection.count_documents({"section": section, "status": "resolved"})

    # Generate new cases if we haven't reached the target of 3 resolved cases
    if resolved_count < 3:
        for i in range(resolved_count, 3):
            print(f"➡️ Generating new case {i+1} for Section {section}")
            success = False
            retries = 0
            
            while not success and retries < max_retries_per_case:
                try:
                    print(f"{'🔄 Retrying new case generation' if retries > 0 else '🆕 Generating new case'} (Attempt {retries+1}/{max_retries_per_case})")
                    await run_single_case(section)
                    success = True
                    did_work = True
                except Exception as e:
                    print(f"❌ Error generating new case: {e}")
                    retries += 1
                    await asyncio.sleep(5)
            
            if not success:
                print(f"⛔ Failed to generate new case after {max_retries_per_case} attempts")
                break

    # ⏳ Only wait if something was done
    if did_work:
        print(f"⏳ Waiting 10 seconds before next section...")
        time.sleep(10)

# ---- Run for All Sections ----
async def run_pipeline():
    # Print initial rotation status
    initial_stats = print_initial_rotation_status()
    
    # First, identify sections with incomplete cases
    sections_with_incomplete = []
    for section in ipc_sections:
        incomplete_count = cases_collection.count_documents({
            "section": section, 
            "status": {"$in": ["details-only", "in-progress"]}
        })
        if incomplete_count > 0:
            sections_with_incomplete.append((section, incomplete_count))
    
    # Sort sections by number of incomplete cases (highest first)
    sections_with_incomplete.sort(key=lambda x: x[1], reverse=True)
    sections_to_process_first = [section for section, _ in sections_with_incomplete]
    
    # Process sections with incomplete cases first
    if sections_to_process_first:
        print(f"\n🔄 Processing {len(sections_to_process_first)} sections with incomplete cases first...")
        for section in sections_to_process_first:
            await run_cases_for_section(section)
    
    # Then process remaining sections
    remaining_sections = [s for s in ipc_sections if s not in sections_to_process_first]
    if remaining_sections:
        print(f"\n🆕 Processing {len(remaining_sections)} remaining sections...")
        for section in remaining_sections:
            await run_cases_for_section(section)
    
    # Print final rotation status
    print("\n🏁 Pipeline run completed!")
    print_final_rotation_status(initial_stats)

if __name__ == "__main__":
    asyncio.run(run_pipeline())

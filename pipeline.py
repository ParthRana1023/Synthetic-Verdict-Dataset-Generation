# pipeline.py
import asyncio
import time
import json
import os
from pymongo import MongoClient, errors
from bson import ObjectId
from dotenv import load_dotenv
from llm_manager import rotate_key

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

# ---- Retry Decorator ----
def retry_with_backoff(func):
    async def wrapper(*args, **kwargs):
        retries, delay = 3, 2
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()

                # Rate limit -> stop pipeline
                if "rate limit" in error_str:
                    print(f"⛔ Pipeline stopped: Rate limit reached - {e}")
                    raise SystemExit("Stopping pipeline due to LLM rate limit.")

                # 503 over capacity -> retry with backoff
                elif "503" in error_str or "over capacity" in error_str:
                    print(f"⚠️ LLM over capacity. Retrying in {delay}s (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                    delay *= 2

                else:
                    print(f"❌ Error: {e}")
                    return None

        return None
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
        if is_valid_response(resp):
            plaintiff_args.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)

    if len(defendant_args) == 0:
        print("🟢 Generating Defendant Opening...")
        resp = await opening_statement("Defendant", case_details, "Plaintiff")
        if is_valid_response(resp):
            defendant_args.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)

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
        if is_valid_response(arg_p):
            plaintiff_args.append(arg_p)
            history.append(arg_p)
            save_progress(case_id, plaintiff_args, defendant_args)

        print(f"🔶 Defendant Counter {round_num}")
        arg_d = await generate_counter_argument(
            "\n".join(history),
            arg_p,
            "Defendant",
            "Plaintiff",
            case_details
        )
        if is_valid_response(arg_d):
            defendant_args.append(arg_d)
            history.append(arg_d)
            save_progress(case_id, plaintiff_args, defendant_args)

    # Step 3: Closings
    if len(plaintiff_args) < 4:
        print("\n🟢 Generating Plaintiff Closing...")
        resp = await closing_statement("\n".join(history), "Plaintiff", "Defendant")
        if is_valid_response(resp):
            plaintiff_args.append(resp)
            history.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)

    if len(defendant_args) < 4:
        print("🟢 Generating Defendant Closing...")
        resp = await closing_statement("\n".join(history), "Defendant", "Plaintiff")
        if is_valid_response(resp):
            defendant_args.append(resp)
            history.append(resp)
            save_progress(case_id, plaintiff_args, defendant_args)

    # Step 4: Mark resolved only if both sides have 4 entries
    if len(plaintiff_args) == 4 and len(defendant_args) == 4:
        save_progress(case_id, plaintiff_args, defendant_args, status="resolved")
        print(f"✅ Case {case_id} marked RESOLVED.")
    else:
        print(f"⚠️ Case {case_id} incomplete. Will retry missing arguments next run.")

# ---- Generate a New Case ----
@retry_with_backoff
async def run_single_case(section: int):
    print(f"\n📂 Creating new case for Section {section}...")
    case = await generate_case(1, [section])

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
        return None

    # Immediately generate arguments
    await generate_arguments_for_case(case_data)

# ---- Run for a Single Section ----
async def run_cases_for_section(section: int):
    # Fetch all cases for this section (including resolved ones)
    existing_cases = list(cases_collection.find({"section": section}))

    # Split into resolved and incomplete
    resolved = [c for c in existing_cases if c.get("status") == "resolved"]
    incomplete = [c for c in existing_cases if c.get("status") != "resolved"]

    print(f"\n📊 Section {section}: {len(resolved)} resolved, {len(incomplete)} incomplete cases in DB")

    # Complete any incomplete cases first
    for case in incomplete:
        await generate_arguments_for_case(case)

    # Count resolved cases again after processing
    resolved_count = cases_collection.count_documents({"section": section, "status": "resolved"})

    # Ensure exactly 3 resolved cases exist
    if resolved_count < 3:
        for i in range(resolved_count, 3):
            print(f"➡️ Generating new case {i+1} for Section {section}")
            await run_single_case(section)

# ---- Run for All Sections ----
async def run_pipeline():
    for section in ipc_sections:
        await run_cases_for_section(section)

if __name__ == "__main__":
    asyncio.run(run_pipeline())

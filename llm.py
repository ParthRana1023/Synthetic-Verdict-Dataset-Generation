from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from llm_manager import get_current_key

load_dotenv()

# Initialize LLM before functions that use it
# groq_api_key = os.getenv(get_current_key())

# Initialize LLM
llm = ChatGroq(
    streaming=True,
    model="llama-3.1-8b-instant",
    temperature=0.1,
    api_key=get_current_key(),
    max_tokens=2048
)

# Models tested: llama-3.3-70b-versatile (best), llama-3.1-8b-instant (good)
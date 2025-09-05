from langchain_groq import ChatGroq
from llm_manager import get_current_key, get_current_model

# Function to get a fresh LLM instance with current model and key
def get_llm():
    # Get a new instance each time to ensure we use the latest model and key
    return ChatGroq(
        streaming=True,
        model=get_current_model(),
        temperature=0.1,
        api_key=get_current_key(),
        max_tokens=2048
    )

# Models tested: llama-3.3-70b-versatile (best), llama-3.1-8b-instant (good)
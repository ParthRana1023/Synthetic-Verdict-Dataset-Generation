import logging
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm import get_llm

logger = logging.getLogger(__name__)

# ---- Argument Generation ----
async def generate_counter_argument(history: str, last_argument: str, ai_role: str = None, user_role: str = None, case_details: str = None) -> str:
    try:
        template = '''You are an experienced and assertive Indian trial lawyer representing the {ai_role}. 
        The opposing lawyer represents the {user_role}. 
        The case details are: {case_details}
        Argument history so far: {history} 

        The last argument made was: "{last_argument}"

        Your task: Respond directly to the last argument in a logical and coherent manner. 
        Build upon earlier arguments but do not repeat them. 
        Keep the response under 200 words. 
        Don't add headings like "Counter Argument".
        '''
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", template)
        ]) 

        chain = prompt | get_llm() | StrOutputParser()

        response = chain.invoke({
            "ai_role": ai_role,
            "history": history,
            "case_details": case_details,
            "user_role": user_role,
            "last_argument": last_argument
        })
        
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        return response
    except Exception as e:
        logger.error(f"Error generating counter argument: {str(e)}")
        return "I apologize, but I'm unable to generate a counter argument at this time. Please try again later."

# ---- Opening Statement ----
async def opening_statement(ai_role: str, case_details: str, user_role: str) -> str:
    try:
        template = '''You are an Indian lawyer from the {ai_role}'s side. 
        Provide a strong and concise opening statement (under 250 words) using these case details: {case_details}. 
        The opposing lawyer represents the {user_role}. 
        Stay strictly within the facts of the case. 
        Do not add headings like "Opening Statement".
        '''
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", template)
        ])

        chain = prompt | get_llm() | StrOutputParser()

        response = chain.invoke({
            'ai_role': ai_role,
            'case_details': case_details,
            'user_role': user_role
        })

        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        return response
    except Exception as e:
        logger.error(f"Error generating opening statement: {str(e)}")
        return "I apologize, but I'm unable to generate an opening statement at this time. Please try again later."

# ---- Closing Statement ----
async def closing_statement(history: str, ai_role: str, user_role: str) -> str:
    try:
        # Truncate history if it's too long to avoid token limits
        if len(history) > 15000:  # Approximate token limit safety
            logger.info(f"History too long ({len(history)} chars), truncating for closing statement")
            # Keep the beginning context and the most recent arguments
            parts = history.split('\n\n')
            if len(parts) > 6:
                # Keep intro + last 5 argument blocks
                truncated = parts[0] + '\n\n' + '\n\n'.join(parts[-5:])
                history = truncated
                logger.info(f"Truncated history to {len(history)} chars")

        template = '''You are an Indian lawyer from the {ai_role}'s side. 
        Provide a powerful closing statement (around 250 words) based on the full case history: {history}. 
        Summarize your strongest points and highlight evidence. 
        The opposing lawyer represents the {user_role}. 
        End your statement with: "I rest my case here". 
        Do not add headings like "Closing Statement".
        '''
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", template)
        ])

        chain = prompt | get_llm() | StrOutputParser()

        response = chain.invoke({
            'ai_role': ai_role,
            'history': history,
            'user_role': user_role
        })

        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        
        # Verify we got a valid response
        if not response or len(response) < 50 or "apologize" in response.lower():
            logger.warning(f"Received potentially invalid closing statement: {response[:50]}...")
            raise ValueError("Invalid closing statement response")
            
        return response
    except Exception as e:
        # Let the retry decorator handle this exception
        logger.error(f"Error generating closing statement: {str(e)}")
        raise e

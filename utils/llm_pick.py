from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

def pick_llm(level: str):
    """
    Pick the appropriate LLM based on the level of complexity.

    Args:
        level (str): The level of complexity ('simple', 'intermediate', 'complex').

    Returns:
        str: The name of the selected LLM.
    """
    if level.lower() == 'low':
        llm = ChatOpenAI(model_name="gpt-5.6-luna", temperature=0)
    elif level.lower() == 'medium':
        llm = ChatOpenAI(model_name="gpt-5.6-terra", temperature=0)
    elif level == 'high':
        llm = ChatOpenAI(model_name="gpt-5.6-sol", temperature=0)
    else:
        raise ValueError(f"Unsupported level: {level}")
    
    return llm

if __name__ == "__main__":
    llm_obj = pick_llm("low")
    print(llm_obj.invoke("what is the capital of UK?"))
    


      
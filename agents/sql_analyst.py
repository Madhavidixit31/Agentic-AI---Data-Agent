import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.llm_pick import pick_llm
from utils.database import DatabaseUtil
from Models.Schema import AgentSchema, JudgeSchema 
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END

#-------------------- AI Agent Code --------------------#

def curate_ques(state: AgentSchema) -> AgentSchema:
    """
    Curate the user question to ensure it is clear and unambiguous.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    user_question = state.user_questions # this is pydantic model object

    llm = pick_llm("low")  # Pick the appropriate LLM based on the level of complexity

    response = llm.invoke(f"Curate the following user question: {user_question}").content

    state.curated_ques = response  # Update the state with the curated question
    state.messages = state.messages + [HumanMessage(content=f"{response}")]  # Append the curated question to the messages

    return state  # Return the updated state


def prompt_query_context(state: AgentSchema) -> AgentSchema:
    """
    Generate a detailed prompt with SQL DB context to be used for generating the query.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    curated_question = state.curated_ques  # Get the curated question from the state

    conn_details = {
        "host": os.environ.get('host'),
        "port": os.environ.get('port'),
        "dbname": os.environ.get('database'),
        "user": os.environ.get('user'),
        "password": os.environ.get('password')
    }

    obj = DatabaseUtil(conn_details)

    schema_info = obj.schema_details("public")  # Get the schema information for the 'public' schema

    #construct the prompt query for the agent to generate the SQL query

    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.  
    
    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    
    """    
    state.prompt_query_context = prompt  # Update the state with the generated prompt

    return state  # Return the updated state

def generate_sql(state: AgentSchema) -> AgentSchema:
    """
    Generate the SQL query based on the user's question and the database schema.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    prompt = state.prompt_query_context  # Get the prompt query context from the state

    llm = pick_llm("medium")  # Pick the appropriate LLM based on the level of complexity

    generated_sql_query = llm.invoke(prompt).content  # Generate the SQL query using the LLM

    state.generated_sql_query = generated_sql_query  # Update the state with the generated SQL query

    return state  # Return the updated state

# IS SQL SAFE Node

def is_safe_sql(state: AgentSchema) -> AgentSchema:
    """
    Determine whether the generated SQL query is safe to execute.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    sql_query = state.generated_sql_query  # Get the generated SQL query from the state

    llm = pick_llm("medium")  # Pick the appropriate LLM based on the level of complexity
    llm_judge = llm.with_structured_output(JudgeSchema)  # Create a structured output LLM for judging SQL safety

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is safe or not. 
    The SQL query should only be used for data retrieval and should not modify the database in any way.
    Neither the query nor the prompt should contain any SQL commands that can modify the database,
    such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change the structure or
    content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 'No'. 
    Additionally, provide comments or reasoning for your decision.
    
    Here is the SQL query to evaluate:
    {sql_query}
    """ 

    response = llm_judge.invoke(prompt).model_dump()  # Get the response from the LLM and get the structure output as dictionary

    # Assuming response is a structured output with 'answer' and 'comments'
    state.is_safe = response['answer']  # Update the state with whether the query is safe
    state.comments = response['comments']  # Update the state with comments or reasoning

    return state  # Return the updated state

def canceled_sql(state: AgentSchema) -> AgentSchema:
    """
    Handle the case where the SQL query is deemed unsafe.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    comments = state.comments  # Get the comments from the state

    state.final_answer = f"The SQL query was deemed unsafe to execute. Reasoning: {comments}"  # Update the state with the final answer
    state.messages = state.messages + [AIMessage(content=f"{state.final_answer}")]  # Append the final answer to the messages

    return state  # Return the updated state

def execute_sql(state: AgentSchema) -> AgentSchema:
    """
    Execute the generated SQL query if it is deemed safe.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    sql_query = state.generated_sql_query  # Get the generated SQL query from the state

    conn_details = {
        "host": os.environ.get('host'),
        "port": os.environ.get('port'),
        "user": os.environ.get('user'),
        "password": os.environ.get('password'),
        "dbname": os.environ.get('database')
    }

    obj = DatabaseUtil(conn_details)

    #execution_result = obj.execute_sql(sql_query)  # Execute the SQL query using the DatabaseUtil
    execution_result = obj.execute_sql(sql_query)

    state.sql_query_execution_result = execution_result  # Update the state with the execution result

    return state  # Return the updated state

#Represent the final answer Node
def represent_final_answer(state: AgentSchema) -> AgentSchema:
    """
    Represent the final answer based on the SQL query execution result.

    Args:
        state (AgentSchema): The current state of the agent.
    """
    execution_result = state.sql_query_execution_result  # Get the execution result from the state
    curated_question = state.curated_ques  # Get the curated question from the state

    llm = pick_llm("low")  # Pick the appropriate LLM based on the level of complexity

    prompt = f"""
    You are a SQL analyst agent. Your task is to provide a final answer to the user based on the SQL query execution result.
    and the user's original question. The final answer should be clear, concise, and directly address the user's query.
    Avoid including any SQL code or technical details in the final answer. The final answer should be in a user-friendly format, 
    that is easy to understand for someone without technical knowledge of SQL or databases.
    If the execution result is empty or does not provide a clear answer to the user's questions, explain this in the final answer and provide any relevant information that can help the user understand the situation.\n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """
    llm_response = llm.invoke(prompt).content # Get the response from the LLM

    state.final_answer = llm_response  # Update the state with the final answer
    state.messages = state.messages + [AIMessage(content=f"{llm_response}")]  # Append the final answer to the messages

    return state  # Return the updated state

# ---------------------- Graph Representation of the Agent ---------------------- #
sql_agent_graph = StateGraph(AgentSchema)

#Nodes
sql_agent_graph.add_node("curate_ques", curate_ques)
sql_agent_graph.add_node("prompt_query_context", prompt_query_context)
sql_agent_graph.add_node("generate_sql", generate_sql)
sql_agent_graph.add_node("is_safe_sql", is_safe_sql)
sql_agent_graph.add_node("canceled_sql", canceled_sql)
sql_agent_graph.add_node("execute_sql", execute_sql)
sql_agent_graph.add_node("represent_final_answer", represent_final_answer)

#egdes
sql_agent_graph.add_edge(START, "curate_ques")
sql_agent_graph.add_edge("curate_ques", "prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")

#conditional edges based on the safety of the SQL query
def is_safe_sql_edge(state: AgentSchema) -> str:
    is_safe = state.is_safe  # Get the safety response from the state

    if is_safe.lower() == "yes":
        return "execute_sql"
    else:
        return "canceled_sql"

sql_agent_graph.add_conditional_edges("is_safe_sql", is_safe_sql_edge,
                                      {
                                          "execute_sql": "execute_sql",
                                          "canceled_sql": "canceled_sql"
                                      })

#sql_agent_graph.add_edge("is_safe_sql", "execute_sql")
#sql_agent_graph.add_edge("is_safe_sql", "canceled_sql")

sql_agent_graph.add_edge("canceled_sql", END)
sql_agent_graph.add_edge("execute_sql", "represent_final_answer")

sql_agent_graph.add_edge("represent_final_answer", END)

#compile the graph
sql_analyst = sql_agent_graph.compile()

if __name__ == "__main__":


    from IPython.display import display, Image
    img = Image(sql_analyst.get_graph().draw_mermaid_png())
    with open("sql_analyst_graph.png", "wb") as f:
        f.write(img.data)

    input_schema = {
        "messages": [],
        "user_questions": "What are the different types of payment methods we have in our database?",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }   

    # Execute the graph
    sql_analyst_response = sql_analyst.invoke(input_schema)
    print(sql_analyst_response['messages']) #print the final output of the graph execution

    print("*******************************")

    print(sql_analyst_response['generated_sql_query']) #print the generated SQL query

    print("*******************************")

    print(sql_analyst_response['sql_query_execution_result']) #print the result of executing the SQL query

    print("*******************************")

    print(sql_analyst_response['prompt_query_context'])


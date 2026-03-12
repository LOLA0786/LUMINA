from langchain_core.tools import tool
from neo4j import GraphDatabase, basic_auth
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from root or wherever you place it

class Neo4jConnectionError(Exception):
    """Custom exception for connection issues."""
    pass

@tool
def query_user_financials(user_id: str, cypher: str) -> List[Dict[str, Any]]:
    """
    Execute a **read-only** Cypher query against the user's financial knowledge graph.
    
    Important rules enforced:
    - Query must be a READ operation (MATCH, RETURN, WITH, UNWIND, etc.)
    - Must contain $userId parameter
    - No WRITE, CREATE, MERGE, DELETE, REMOVE allowed
    
    Returns: List of dictionaries (each row as dict)
    """
    # Validate cypher (basic safety - expand later with full parser if needed)
    forbidden = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL"]
    if any(word.upper() in cypher.upper() for word in forbidden):
        raise ValueError("Write operations are forbidden in this tool.")

    if "$userId" not in cypher:
        raise ValueError("Cypher query must use $userId parameter for safety.")

    # Get credentials from environment (never hard-code!)
    uri      = os.getenv("NEO4J_URI",     "bolt://localhost:7687")
    username = os.getenv("NEO4J_USER",    "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise Neo4jConnectionError("NEO4J_PASSWORD not set in .env")

    driver = None
    try:
        driver = GraphDatabase.driver(
            uri,
            auth=basic_auth(username, password),
            # Recommended: add connection pooling & timeout config later
        )
        
        with driver.session(database="neo4j") as session:  # change db name if using multi-db
            # Run with explicit parameter
            result = session.run(cypher, userId=user_id)
            return [dict(record) for record in result]  # convert to clean dicts

    except Exception as e:
        raise Neo4jConnectionError(f"Query failed: {str(e)}") from e
    
    finally:
        if driver:
            driver.close()

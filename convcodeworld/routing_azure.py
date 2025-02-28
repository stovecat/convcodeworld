import functools
import logging
import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from snowflake.connector import connect
from snowflake.snowpark import Session
from flask import Flask, request, jsonify
import subprocess

@dataclass
class ConnectionParameters:
    # ... [previous ConnectionParameters code remains the same] ...
    account: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_ACCOUNT", "")
    )
    user: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_USER", "")
    )
    password: Optional[str] = field(
        repr=False,
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_PASSWORD", ""),
    )
    role: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_ROLE", "")
    )
    warehouse: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_WAREHOUSE", "")
    )
    database: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_DATABASE", "")
    )
    schema: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_SCHEMA", "")
    )
    host: Optional[str] = field(
        default_factory=functools.partial(os.environ.get, "SNOWFLAKE_HOST", "")
    )
    externalbrowser: Optional[str] = field(
        default_factory=functools.partial(
            os.environ.get, "SNOWFLAKE_EXTERNALBROWSER", "false"
        )
    )

    def create_session(self, client_session_keep_alive=False) -> Session:
        """
        Validate that all parameters are provided and create a snowpark session
        """
        params = asdict(self)
        for k, v in params.items():
            if not v:
                if k == "password":
                    if params["externalbrowser"] == "true":
                        continue
                    else:
                        raise Exception(
                            f"environment variable SNOWFLAKE_{k.upper()} is required when not using externalbrowser"
                        )
                raise Exception(
                    f"environment variable SNOWFLAKE_{k.upper()} is required"
                )
        params["client_session_keep_alive"] = client_session_keep_alive
        logging.info(f"Connecting to session using {self}")
        if params["externalbrowser"] == "true":
            connection = connect(**params, authenticator="externalbrowser")
        else:
            connection = connect(**params)
        session = Session.builder.configs({"connection": connection}).create()
        return session

@dataclass
class LLMRouter:
    connection_parameters: ConnectionParameters
    port: int = 7877  # Default port is 7877, but can be customized

    def execute_sql(self, sql_commands: List[str]) -> list:
        """
        Executes SQL commands in Snowflake and collects the results.
        """
        results = []
        session = self.connection_parameters.create_session()
        for command in sql_commands:
            logging.info(f"Executing command: {command}")
            df = session.sql(command)
            results.append(df.collect())
        session.close()
        return results

    def generate_response(self, messages: str, parameters: Optional[dict] = None) -> str:
        """
        Send user input to the Snowflake Cortex AI and fetch the model's response.
        The user_input is treated as the direct message content.
        """
        #messages = [{"role": "user", "content": user_input}]
        
        if not parameters:
            parameters = {"guardrails": False}

        print("[MESSAGES]")
        print(messages)
        
        # Create the SQL command for invoking the Snowflake Cortex model
        sql_command = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'deepseek-r1',
            parse_json('{json.dumps(messages).replace("'", "''").replace('\\n', ' ')}'),
            parse_json('{json.dumps(parameters).replace("'", "''")}')
        );
        """
        
        # Execute the SQL command and get the result
        result = self.execute_sql([sql_command])
        print("[RESULT]")
        print(result)
        return result if result else "No response received."

# Create a Flask application to receive and send back responses
app = Flask(__name__)

@app.route('/v1/chat/completions', methods=['POST'])
def query():
    """
    Endpoint that handles POST requests at /v1 to process user input and return response.
    """
    # Get JSON data from the request body
    data = request.get_json()
    
    if not data or 'messages' not in data:
        print(data)
        return jsonify({'error': 'Invalid input. Please provide messages.'}), 400
    
    messages = data['messages']
    parameters = {'temperature': data['temperature'], "guardrails": False} 
    
    # Set up connection parameters
    cp = ConnectionParameters()
    cp.password = subprocess.check_output("echo ${SNOWFLAKE_PASSWORD}", shell=True).decode()[:-1]
    
    # Create LLMRouter instance with customizable port
    llm_router = LLMRouter(connection_parameters=cp, port=app.config['PORT'])
    
    # Get response from the model
    response = llm_router.generate_response(messages, parameters)
    
    # Return the response to the user
    return jsonify({'response': response})

if __name__ == '__main__':
    # Set the port for the Flask application (default is 7877)
    app.config['PORT'] = 7877
    app.run(host='0.0.0.0', port=app.config['PORT'])

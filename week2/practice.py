import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
import sqlite3

load_dotenv(override=True)

api_key = os.getenv("OPENROUTER_API_KEY")
api_url = os.getenv("OPENROUTER_API_BASE")

# find current script directory and create path to database
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, "prices.db")
DB = db_path

# Check the key

if not api_key:
    print("No API key was found - please head over to the troubleshooting notebook in this folder to identify & fix!")
    os.exit(1)
elif not api_key.startswith("sk-"):
    print("An API key was found, but it doesn't start sk-; please check you're using the right key - see troubleshooting notebook")
    os.exit(1)
elif api_key.strip() != api_key:
    print("An API key was found, but it looks like it might have space or tab characters at the start or end - please remove them - see troubleshooting notebook")
    os.exit(1)
else:
    print("API key found and looks good so far!")

MODEL = "openai/gpt-4.1-mini"
openai = OpenAI(base_url=api_url, api_key=api_key)


system_message = """
You are a helpful assistant for an Airline called FlightAI.
Give short, courteous answers, no more than 1 sentence.
Always be accurate. If you don't know the answer, say so.
"""


def get_ticket_price(destination_city):
    print(f"DATABASE TOOL CALLED: Getting price for {destination_city}", flush=True)
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM prices WHERE city = ?', (destination_city.lower(),))
        result = cursor.fetchone()
        return f"Ticket price to {destination_city} is ${result[0]}" if result else "No price data available for this city"
    

# function to give the list of cities we have prices for
def list_cities():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT city FROM prices')
        result = cursor.fetchall()
        cities = [row[0].capitalize() for row in result]
        print(f"DATABASE TOOL CALLED: Listing cities with price data - found {len(cities)} cities", flush=True)
        return "We have ticket price data for the following cities: " + ", ".join(cities)
    

list_cities_function = {
    "name": "list_cities",
    "description": "List the cities that we have ticket price data for.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }
}

price_function = {
    "name": "get_ticket_price",
    "description": "Get the price of a return ticket to the destination city.",
    "parameters": {
        "type": "object",
        "properties": {
            "destination_city": {
                "type": "string",
                "description": "The city that the customer wants to travel to",
            },
        },
        "required": ["destination_city"],
        "additionalProperties": False
    }
}

tools = [
    {"type": "function", "function": price_function},
    {"type": "function", "function": list_cities_function}
]

print(list_cities())
print(get_ticket_price("London"))

def handle_tool_calls(message):
    print(message)
    responses = []
    
    available_functions = {
        "get_ticket_price": get_ticket_price,
        "list_cities": list_cities
    }
    
    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        function_to_call = available_functions.get(function_name)
        if function_to_call:
            arguments = json.loads(tool_call.function.arguments)
            result = function_to_call(**arguments)
            responses.append({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tool_call.id
            })
    return responses

def chat(message, history):
    history = [{"role":h["role"], "content":h["content"]} for h in history]
    messages = [{"role": "system", "content": system_message}] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)

    while response.choices[0].finish_reason=="tool_calls":
        message = response.choices[0].message
        responses = handle_tool_calls(message)
        messages.append(message)
        messages.extend(responses)
        response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)
    
    return response.choices[0].message.content

gr.ChatInterface(fn=chat, type="messages").launch()
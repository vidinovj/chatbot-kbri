# Import the necessary libraries
import streamlit as st
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

# --- 1. Page Configuration and Title ---
st.set_page_config(page_title="KBRI/KJRI Finder Chatbot", page_icon="🇮🇩")
st.title("🇮🇩 KBRI/KJRI Finder Chatbot")
st.caption("Your friendly assistant to find the nearest Indonesian embassy or consulate.")

# --- 2. Sidebar for Settings ---
with st.sidebar:
    st.subheader("Settings")
    google_api_key = st.text_input("Google AI API Key", type="password", key="google_api_key")
    reset_button = st.button("Reset Conversation", key="reset_button")

# --- 3. Data Loading ---
@st.cache_data
def load_data():
    kbri_kjri_df = pd.read_csv("kbri_kjri_locations_with_coordinates.csv")
    world_cities_df = pd.read_csv("world_cities.csv")
    return kbri_kjri_df, world_cities_df

kbri_kjri_df, world_cities_df = load_data()

# --- 4. Geolocation Tool ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

@tool
def find_nearest_kbri_kjri(city_name: str):
    """Finds the nearest Indonesian embassy (KBRI) or consulate (KJRI) from a given city."""
    
    # ✅ Better city matching - handle variations
    city_search = city_name.lower().strip()
    
    # Try exact match first
    user_city_data = world_cities_df[
        world_cities_df["name"].str.lower() == city_search
    ]
    
    # If no exact match, try contains (for partial matches)
    if user_city_data.empty:
        user_city_data = world_cities_df[
            world_cities_df["name"].str.lower().str.contains(city_search, na=False)
        ]
    
    # If still no match, try matching against country or admin (state) names
    if user_city_data.empty:
        # Look for the largest city in that state/region
        user_city_data = world_cities_df[
            (world_cities_df["admin_name"].str.lower().str.contains(city_search, na=False)) |
            (world_cities_df["country"].str.lower().str.contains(city_search, na=False))
        ].nlargest(1, 'population')  # Get the largest city
    
    if user_city_data.empty:
        return f"Sorry, I couldn't find the city '{city_name}' in my database. Please try providing a major city name."
    
    try:
        user_city_data = user_city_data.iloc[0]
        user_lat, user_lon = user_city_data["lat"], user_city_data["lng"]
    except (IndexError, KeyError) as e:
        return f"Sorry, I encountered an error finding coordinates for '{city_name}'."

    distances = []
    for index, row in kbri_kjri_df.iterrows():
        dist = haversine(user_lat, user_lon, row["Latitude"], row["Longitude"])
        distances.append((row["City"], row["Country"], row["Type"], dist))

    distances.sort(key=lambda x: x[3])
    
    # ✅ Return top 3 nearest offices for better context
    top_3 = distances[:3]
    result = f"The nearest Indonesian representative office is a {top_3[0][2]} in {top_3[0][0]}, {top_3[0][1]}, which is approximately {top_3[0][3]:.2f} km away."
    
    if len(top_3) > 1:
        result += f"\n\nOther nearby offices:\n"
        for i, (city, country, type, dist) in enumerate(top_3[1:], 2):
            result += f"{i}. {type} in {city}, {country} ({dist:.2f} km)\n"
    
    return result

@tool
def extract_city_from_prompt(user_prompt: str):
    """Extracts the city name from a user's prompt."""
    extraction_prompt = f"From the following text, extract the most likely city name. If no city is mentioned, or if the location is ambiguous (like a state or an island), return the name of the largest city in that area. For example, if the user says 'Jersey', you should return 'Saint Helier'. If the user says 'New Jersey', you should return 'Newark'. Return only the city name and nothing else: \"{user_prompt}\""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=extraction_prompt
    )
    return response.text.strip()

# --- 5. Agent Initialization ---
if not google_api_key:
    st.info("Please add your Google AI API key to start chatting.")
    st.stop()

if "agent" not in st.session_state or getattr(st.session_state, "_last_key", None) != google_api_key:
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=google_api_key, temperature=0.7)
        tools = [find_nearest_kbri_kjri, extract_city_from_prompt]
        st.session_state.agent = create_react_agent(llm, tools, prompt="""You are a helpful assistant for Indonesians abroad. Your goal is to help users find the nearest Indonesian embassy (KBRI) or consulate (KJRI).

When a user asks for the nearest location, you should:
1. Use the `extract_city_from_prompt` tool to extract the city from the user's query.
2. Use the `find_nearest_kbri_kjri` tool with the extracted city name to find the nearest office.
3. After getting the result from the tool, you should analyze it. If the nearest office is in a different country, you should also consider if there are other offices in the user's country that might be more convenient, even if they are slightly further away.
4. Provide a helpful and informative response in Indonesian. You should clearly state the nearest office, but also provide information about other relevant offices if applicable.
5. If the user mentions that they have lost their passport, you should provide general advice on what to do, such as contacting the local police and the nearest Indonesian representative office.
""")
        st.session_state._last_key = google_api_key
        st.session_state.messages = []
    except Exception as e:
        st.error(f"Error initializing the agent: {e}")
        st.stop()

# --- 6. Chat History Management ---
if reset_button:
    st.session_state.messages = []

# --- 7. Display Past Messages ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

# --- 8. Handle User Input ---
if prompt := st.chat_input("Ask me to find the nearest KBRI/KJRI..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                messages = [HumanMessage(content=prompt)] if not st.session_state.messages else [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]) for m in st.session_state.messages]
                response = st.session_state.agent.invoke({"messages": messages})
                ai_message = response["messages"][-1]
                
                # ✅ FIXED: Better content extraction
                answer = ""
                if hasattr(ai_message, 'content'):
                    content = ai_message.content
                    
                    # If content is a list of parts
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict):
                                # Only extract 'text' field, ignore 'extras'
                                if 'text' in part:
                                    answer += part['text']
                            elif isinstance(part, str):
                                answer += part
                    
                    # If content is a string
                    elif isinstance(content, str):
                        answer = content
                    
                    # If content is something else, convert to string
                    else:
                        answer = str(content)
                
                # Clean up any remaining metadata
                if not answer or "signature" in answer.lower():
                    # Fallback: try to get just the text portion
                    if hasattr(ai_message, 'content') and isinstance(ai_message.content, list):
                        texts = [p.get('text', '') for p in ai_message.content if isinstance(p, dict) and 'text' in p]
                        answer = ' '.join(texts)

                if not answer:
                    answer = "Sorry, I encountered an error and could not generate a response."

                st.markdown(answer)
            except Exception as e:
                st.error(f"An error occurred: {e}")
                answer = "Sorry, I encountered an error."
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
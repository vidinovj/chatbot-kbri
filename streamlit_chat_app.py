# Import the necessary libraries
import streamlit as st
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from google import genai

# --- 1. Page Configuration and Title ---

st.title("Kantor Perwakilan RI Terdekat")
st.caption("Cari Kedutaan Besar atau Konsulat Jenderal RI terdekat dari lokasimu")

# --- 2. Sidebar for Settings ---

with st.sidebar:
    st.subheader("Settings")
    google_api_key = st.text_input("Google AI API Key", type="password")

# --- 3. API Key and Client Initialization ---

if not google_api_key:
    st.info("Please add your Google AI API key in the sidebar to start chatting.", icon="🗝️")
    st.stop()

try:
    client = genai.Client(api_key=google_api_key)
except Exception as e:
    st.error(f"Invalid API Key: {e}")
    st.stop()

# --- 4. Data Loading ---

@st.cache_data
def load_data():
    kbri_kjri_df = pd.read_csv("kbri_kjri_locations_with_coordinates.csv")
    world_cities_df = pd.read_csv("world_cities.csv")
    return kbri_kjri_df, world_cities_df

kbri_kjri_df, world_cities_df = load_data()

# --- 5. Core Logic ---

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance

def find_nearest_kbri_kjri(user_prompt):
    # Use Gemini to extract the city from the user's prompt
    extraction_prompt = f"From the following text, extract only the city name and nothing else: \"{user_prompt}\""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=extraction_prompt
        )
        user_city = response.text.strip()
    except Exception as e:
        return f"An error occurred while extracting the city: {e}", None, None

    try:
        user_city_data = world_cities_df[world_cities_df["name"].str.lower() == user_city.lower()].iloc[0]
        user_lat, user_lon = user_city_data["lat"], user_city_data["lng"]
    except IndexError:
        return f"Maaf, saya tidak dapat menemukan kota '{user_city}' dalam database saya.", None, None

    distances = []
    for index, row in kbri_kjri_df.iterrows():
        dist = haversine(user_lat, user_lon, row["Latitude"], row["Longitude"])
        distances.append((row["City"], row["Country"], row["Type"], dist))

    distances.sort(key=lambda x: x[3])
    nearest = distances[0]
    return None, nearest, (user_lat, user_lon)


# --- 6. Chat History Management ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 7. Display Past Messages ---

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 8. Handle User Input ---

prompt = st.chat_input("Contoh: Saya di Paris, di mana KBRI terdekat?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    error_message, nearest, user_coords = find_nearest_kbri_kjri(prompt)

    if error_message:
        answer = error_message
    elif nearest:
        city, country, type, dist = nearest
        
        # Use Gemini to generate a richer response
        generation_prompt = f"You are a helpful assistant for Indonesians abroad. Based on the following information, generate a friendly and informative response in Indonesian. The user is in {prompt}. The nearest Indonesian representative office is a {type} in {city}, {country}, which is approximately {dist:.2f} km away. Provide the information clearly and maybe add a helpful tip about the location."
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=generation_prompt
            )
            answer = response.text
        except Exception as e:
            answer = f"An error occurred while generating the response: {e}"
    else:
        answer = "Maaf, saya tidak dapat menemukan informasi yang Anda cari."


    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
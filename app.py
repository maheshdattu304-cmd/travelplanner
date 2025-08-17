import streamlit as st
import json
import os
from serpapi import GoogleSearch
from agno.agent import Agent
from agno.tools.serpapi import SerpApiTools
from agno.models.google import Gemini
from datetime import datetime
# ----------------- Load API keys from Streamlit secrets -----------------
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="🌍 AI Travel Planner", layout="wide")
st.markdown("""
<style>
.title { text-align: center; font-size: 36px; font-weight: bold; color: #ff5733; }
.subtitle { text-align: center; font-size: 20px; color: #555; }
.stSlider > div { background-color: #f9f9f9; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="title">✈️ AI-Powered Travel Planner</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Plan your dream trip with AI! Get recommendations for flights, hotels, and activities.</p>', unsafe_allow_html=True)

# ----------------- User Inputs -----------------
st.markdown("### 🌍 Where are you headed?")
source = st.text_input("🛫 Departure City (IATA Code):", "BOM")
destination = st.text_input("🛬 Destination (IATA Code):", "DEL")

st.markdown("### 📅 Plan Your Adventure")
num_days = st.slider("🕒 Trip Duration (days):", 1, 14, 5)
travel_theme = st.selectbox("🎭 Select Your Travel Theme:", ["💑 Couple Getaway", "👨‍👩‍👧‍👦 Family Vacation", "🏔️ Adventure Trip", "🧳 Solo Exploration"])
activity_preferences = st.text_area("🌍 What activities do you enjoy?", "Relaxing on the beach, exploring historical sites")
departure_date = st.date_input("Departure Date")
return_date = st.date_input("Return Date")

# ----------------- Sidebar -----------------
st.sidebar.title("🌎 Travel Assistant")
budget = st.sidebar.radio("💰 Budget Preference:", ["Economy", "Standard", "Luxury"])
flight_class = st.sidebar.radio("✈️ Flight Class:", ["Economy", "Business", "First Class"])
hotel_rating = st.sidebar.selectbox("🏨 Preferred Hotel Rating:", ["Any", "3⭐", "4⭐", "5⭐"])

st.sidebar.subheader("🎒 Packing Checklist")
packing_list = {
    "👕 Clothes": True,
    "🩴 Comfortable Footwear": True,
    "🕶️ Sunglasses & Sunscreen": False,
    "📖 Travel Guidebook": False,
    "💊 Medications & First-Aid": True
}
for item, checked in packing_list.items():
    st.sidebar.checkbox(item, value=checked)

st.sidebar.subheader("🛂 Travel Essentials")
visa_required = st.sidebar.checkbox("🛃 Check Visa Requirements")
travel_insurance = st.sidebar.checkbox("🛡️ Get Travel Insurance")
currency_converter = st.sidebar.checkbox("💱 Currency Exchange Rates")

# ----------------- Helper Functions -----------------
def format_datetime(iso_string):
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%d %H:%M")
        return dt.strftime("%b-%d, %Y | %I:%M %p")
    except:
        return "N/A"

def fetch_flights(source, destination, departure_date, return_date):
    params = {
        "engine": "google_flights",
        "departure_id": source,
        "arrival_id": destination,
        "outbound_date": str(departure_date),
        "return_date": str(return_date),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results

def extract_cheapest_flights(flight_data):
    best_flights = flight_data.get("best_flights", [])
    return sorted(best_flights, key=lambda x: x.get("price", float("inf")))[:3]

# ----------------- Initialize Agents with Error Handling -----------------
def init_agent(name, instructions, tools=None):
    try:
        return Agent(
            name=name,
            instructions=instructions,
            model=Gemini(id="gemini-1.5-flash"),
            tools=tools or [],
            add_datetime_to_instructions=True,
        )
    except Exception as e:
        st.warning(f"⚠️ Could not access 'gemini-1.5-flash' model. Falling back to 'gemini-1.5'. Error: {e}")
        return Agent(
            name=name,
            instructions=instructions,
            model=Gemini(id="gemini-1.5"),
            tools=tools or [],
            add_datetime_to_instructions=True,
        )

researcher = init_agent(
    name="Researcher",
    instructions=[
        "Research the destination, attractions, activities, culture, and safety.",
        "Provide well-structured travel summaries."
    ],
    tools=[SerpApiTools(api_key=SERPAPI_KEY)]
)

planner = init_agent(
    name="Planner",
    instructions=[
        "Create a detailed itinerary including transportation, activities, and estimated costs."
    ]
)

hotel_restaurant_finder = init_agent(
    name="Hotel & Restaurant Finder",
    instructions=[
        "Find highly rated hotels and restaurants near attractions."
    ],
    tools=[SerpApiTools(api_key=SERPAPI_KEY)]
)

# ----------------- Generate Travel Plan -----------------
if st.button("🚀 Generate Travel Plan"):
    with st.spinner("✈️ Fetching best flight options..."):
        flight_data = fetch_flights(source, destination, departure_date, return_date)
        cheapest_flights = extract_cheapest_flights(flight_data)

    # AI Research
    with st.spinner("🔍 Researching attractions & activities..."):
        research_prompt = (
            f"Research the best attractions and activities in {destination} for a {num_days}-day {travel_theme.lower()} trip. "
            f"Traveler enjoys: {activity_preferences}. Budget: {budget}. Flight Class: {flight_class}. Hotel Rating: {hotel_rating}."
        )
        try:
            research_results = researcher.run(research_prompt, stream=False)
        except Exception as e:
            research_results = type('obj', (object,), {'content': f"⚠️ Research failed: {e}"})()

    # Hotels & Restaurants
    with st.spinner("🏨 Finding hotels & restaurants..."):
        hotel_restaurant_prompt = (
            f"Find best hotels and restaurants near popular attractions in {destination} "
            f"for a {travel_theme.lower()} trip. Budget: {budget}. Hotel Rating: {hotel_rating}."
        )
        try:
            hotel_restaurant_results = hotel_restaurant_finder.run(hotel_restaurant_prompt, stream=False)
        except Exception as e:
            hotel_restaurant_results = type('obj', (object,), {'content': f"⚠️ Hotels & restaurants fetch failed: {e}"})()

    # Create Itinerary
    with st.spinner("🗺️ Creating itinerary..."):
        planning_prompt = (
            f"Create a {num_days}-day itinerary for a {travel_theme.lower()} trip to {destination}. "
            f"Activities: {activity_preferences}. Budget: {budget}. Flight Class: {flight_class}. Hotel Rating: {hotel_rating}. "
            f"Research: {research_results.content}. Flights: {json.dumps(cheapest_flights)}. Hotels & Restaurants: {hotel_restaurant_results.content}."
        )
        try:
            itinerary = planner.run(planning_prompt, stream=False)
        except Exception as e:
            itinerary = type('obj', (object,), {'content': f"⚠️ Itinerary creation failed: {e}"})()

    # ----------------- Display Results -----------------
    st.subheader("✈️ Cheapest Flight Options")
    if cheapest_flights:
        cols = st.columns(len(cheapest_flights))
        for idx, flight in enumerate(cheapest_flights):
            with cols[idx]:
                airline_logo = flight.get("airline_logo", "")
                airline_name = flight.get("airline", "Unknown Airline")
                price = flight.get("price", "Not Available")
                total_duration = flight.get("total_duration", "N/A")
                departure_time = format_datetime(flight.get("departure_time", "N/A"))
                arrival_time = format_datetime(flight.get("arrival_time", "N/A"))
                booking_link = "#"

                st.markdown(f"""
                <div style="border: 2px solid #ddd; border-radius: 10px; padding: 15px; text-align: center;
                            box-shadow: 2px 2px 10px rgba(0,0,0,0.1); background-color: #f9f9f9; margin-bottom: 20px;">
                    <img src="{airline_logo}" width="100" alt="Flight Logo" />
                    <h3 style="margin:10px 0;">{airline_name}</h3>
                    <p><strong>Departure:</strong> {departure_time}</p>
                    <p><strong>Arrival:</strong> {arrival_time}</p>
                    <p><strong>Duration:</strong> {total_duration} min</p>
                    <h2 style="color: #008000;">💰 {price}</h2>
                    <a href="{booking_link}" target="_blank" style="
                        display:inline-block; padding:10px 20px; font-size:16px; font-weight:bold;
                        color:#fff; background-color:#007bff; text-decoration:none; border-radius:5px;
                        margin-top:10px;">🔗 Book Now</a>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ No flight data available.")

    st.subheader("🏨 Hotels & Restaurants")
    st.write(hotel_restaurant_results.content)

    st.subheader("🗺️ Your Personalized Itinerary")
    st.write(itinerary.content)

    st.success("✅ Travel plan generated successfully!")

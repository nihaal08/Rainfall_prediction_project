# openweather_streamlit_test.py

import streamlit as st
import requests

st.set_page_config(page_title="Weather Fetcher", page_icon="🌦️")

st.title("🌦️ OpenWeather API Test")
st.markdown("Enter a city name or your coordinates to get real-time weather data.")

API_KEY = "bd5e378503939ddaee76f12ad7a97608"  # Replace with your OpenWeather API key

# Option to use city or coordinates
option = st.radio("Select input method", ["City Name", "Coordinates"])

if option == "City Name":
    city = st.text_input("City", value="Mangalore")
    if st.button("Get Weather"):
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
elif option == "Coordinates":
    lat = st.number_input("Latitude", format="%.4f")
    lon = st.number_input("Longitude", format="%.4f")
    if st.button("Get Weather"):
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"

# Show results
if "url" in locals():
    try:
        response = requests.get(url)
        data = response.json()

        if response.status_code == 200:
            st.success("✅ Weather Data Fetched Successfully")
            st.metric("Temperature", f"{data['main']['temp']} °C")
            st.metric("Humidity", f"{data['main']['humidity']} %")
            st.metric("Pressure", f"{data['main']['pressure']} hPa")
            st.write("📍 Location:", data['name'])
            st.write("⛅ Description:", data['weather'][0]['description'].capitalize())
        else:
            st.error(f"Failed to fetch weather data: {data.get('message', 'Unknown error')}")
    except Exception as e:
        st.error(f"Error: {e}")

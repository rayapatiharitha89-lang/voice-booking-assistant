"""
Voice Booking Assistant - Flask backend.
Gemini + Google Places search + a real (demo) scheduling system.
"""
import os
import uuid
import json
import threading
from datetime import date as date_cls

import requests
from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai

from flights import search_flights

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
PLACES_API_KEY = os.environ.get("PLACES_API_KEY", GOOGLE_API_KEY)
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-3.6-flash"

CONVERSATIONS = {}

# ---------------------------------------------------------------------------
# A real, working (but self-contained) appointment book. It's not connected
# to any actual clinic's system - it's YOUR app's own calendar, so a booking
# made here genuinely reserves that date/time within this app: try to book
# the same slot twice and the second attempt will be rejected as taken.
# Stored in a JSON file so bookings survive server restarts.
# ---------------------------------------------------------------------------
BOOKINGS_FILE = os.path.join(os.path.dirname(__file__), "bookings.json")
_bookings_lock = threading.Lock()


def _load_bookings():
    if not os.path.exists(BOOKINGS_FILE):
        return []
    with open(BOOKINGS_FILE, "r") as f:
        return json.load(f)


def _save_bookings(bookings):
    with open(BOOKINGS_FILE, "w") as f:
        json.dump(bookings, f, indent=2)


def list_available_slots(date: str) -> str:
    """Check THIS APP's OWN internal appointment book (not any real
    clinic's live system - this is a self-contained calendar you fully
    control) and list several open time slots for a given day, based on
    standard business hours (9:00 AM - 5:00 PM, 30-minute increments) minus
    anything already booked in this app for that day. You CAN and SHOULD
    call this yourself as soon as the caller gives a date - never tell the
    caller you are unable to check. date must be a calendar date like
    '2026-09-25'. Returns up to 6 open times.
    """
    candidate_times = []
    for hour in range(9, 17):
        for minute in (0, 30):
            suffix = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            candidate_times.append(f"{display_hour}:{minute:02d} {suffix}")

    with _bookings_lock:
        bookings = _load_bookings()
    taken = {
        b["time"].strip().lower()
        for b in bookings
        if b["date"].strip().lower() == date.strip().lower()
    }

    open_slots = [t for t in candidate_times if t.lower() not in taken][:6]
    if not open_slots:
        return f"No open slots found for {date} in standard business hours (9 AM - 5 PM). Suggest a different day."
    return f"Open slots for {date}: " + ", ".join(open_slots)


def check_availability(date: str, time: str) -> str:
    """Check whether a given date and time slot is free in the appointment
    book. Always call this BEFORE book_appointment, once the caller has
    given a preferred date and time. date must be a calendar date like
    '2026-09-25'; time should be like '3:00 PM'.
    """
    with _bookings_lock:
        bookings = _load_bookings()
    for b in bookings:
        if b["date"].strip().lower() == date.strip().lower() and b["time"].strip().lower() == time.strip().lower():
            return f"That slot ({date} at {time}) is already booked. Suggest a different time to the caller."
    return f"{date} at {time} is available."


def book_appointment(
    category: str,
    date: str,
    time: str,
    name: str,
    contact: str,
    place_name: str = "",
    place_phone: str = "",
) -> str:
    """Actually reserve a slot in the appointment book once the caller has
    confirmed everything. ALWAYS call check_availability first for the same
    date and time - do not call this if that slot was already reported as
    taken. category is the type of appointment (e.g. 'pediatrician',
    'flight', 'haircut'). place_name/place_phone are optional, from a prior
    search_nearby_places result.
    """
    with _bookings_lock:
        bookings = _load_bookings()
        for b in bookings:
            if b["date"].strip().lower() == date.strip().lower() and b["time"].strip().lower() == time.strip().lower():
                return f"Booking failed - {date} at {time} was just taken. Ask the caller for a different time."

        booking = {
            "id": str(uuid.uuid4())[:8],
            "category": category,
            "date": date,
            "time": time,
            "name": name,
            "contact": contact,
            "place_name": place_name,
            "place_phone": place_phone,
        }
        bookings.append(booking)
        _save_bookings(bookings)

    return f"Booked successfully: {category} for {name} on {date} at {time}. Confirmation ID {booking['id']}."


def search_nearby_places(query: str) -> str:
    """Search for real, currently-operating businesses or clinics matching a
    query such as 'pediatrician near Allentown, PA' or 'dentist in Bethlehem
    PA'. Always include a city, town, or zip code in the query - ask the
    caller for their area first if they have not mentioned one. Returns up
    to 3 real results with name, address, phone number, and rating.
    """
    try:
        search_resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": PLACES_API_KEY},
            timeout=8,
        )
        results = search_resp.json().get("results", [])[:3]
        if not results:
            return "No results found for that search."

        lines = []
        for place in results:
            place_id = place.get("place_id")
            name = place.get("name", "Unknown")
            address = place.get("formatted_address", "")
            rating = place.get("rating", "no rating")

            phone = "phone not listed"
            if place_id:
                details_resp = requests.get(
                    "https://maps.googleapis.com/maps/api/place/details/json",
                    params={
                        "place_id": place_id,
                        "fields": "formatted_phone_number",
                        "key": PLACES_API_KEY,
                    },
                    timeout=8,
                )
                phone = details_resp.json().get("result", {}).get(
                    "formatted_phone_number", "phone not listed"
                )

            lines.append(f"{name} - {address} - {phone} - rating {rating}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Search failed: {exc}"


SYSTEM_PROMPT = """You are a warm, efficient voice booking assistant. You help the caller book ANY kind of appointment - medical, dental, flights, restaurants, haircuts, car service, anything.

CRITICAL RULE - NEVER INVENT FACTS: Never state a specific real-world fact - a business name, address, phone number, airport name, flight number, price, or any other concrete detail - unless it came directly from a tool result you actually called, or from something the caller told you themselves. This applies everywhere, not just place search. If you do not have a real answer for something (e.g. a flight's departure airport, an airline name, a flight number), say plainly that you do not have that information and it is outside what this system can look up - never guess or fill in a plausible-sounding detail.

You have five tools:
- search_nearby_places: looks up REAL nearby businesses (name, address, phone, rating) for anything at a physical location.
- list_available_slots: checks THIS APP's OWN internal appointment book (not the real clinic's live system - a placeholder calendar you fully control) and lists several open time slots for a given day. ALWAYS call this yourself as soon as the caller gives a date. Never tell the caller you cannot check availability - you can and must check via this tool.
- check_availability: checks THIS APP's OWN internal appointment book for one specific date/time. Use this if the caller names an exact time directly instead of picking from a list.
- search_flights: searches flight options between two places on a date (airline, times, stops, price). Use this for ANY flight booking. Never use list_available_slots or check_availability for flight times - those are only for appointments in this app's own calendar.
- book_appointment: ACTUALLY reserves the slot in this app's own calendar. Only call this after a slot is confirmed free and the caller has given their name and contact info.

Your job each conversation:
1. Ask what they would like to book, if they have not said.
2. If it involves a physical place, ask for their city/town/zip if not mentioned, then call search_nearby_places and read back 2-3 real options (name and phone number - skip the full address unless asked). Ask which one they want. NEVER invent, guess, or make up a business name, address, or phone number under any circumstances. If search_nearby_places returns no results or fails, say so honestly and either ask the caller to try a different area, or continue without naming a specific place (leave place_name and place_phone blank in the final booking).
3. FLIGHTS: ask where they are flying from and to, and the date. Convert the date to YYYY-MM-DD using today's date, then call search_flights and read back 2-3 of the options it returns (airline, departure time, price). If the result says it is test data, tell the caller once that these are sample results, not real flights or prices. Never mention an airline, flight number, airport or price that search_flights did not return. Once they pick an option, continue to step 4, and when booking use the chosen flight's departure time and put the airline and route in place_name. Skip check_availability for flights.
   OTHER APPOINTMENTS: ask for their preferred date. IMMEDIATELY call list_available_slots for that date yourself and read back 3-4 of the open times - do not ask the caller if you can check, just check and report the real result. If the caller instead gives an exact time directly, call check_availability for that specific time instead.
4. Once a slot is chosen, ask for their name and a contact phone or email if you do not have them yet.
5. Read the details back once, then call book_appointment to actually reserve it.
6. After a successful booking, tell the caller their confirmation ID, and mention that if this is a real clinic they should still call ahead to confirm since this app's calendar is separate from the clinic's own system.
7. End your reply with a line starting exactly with "BOOKING_CONFIRMED:" followed by a compact JSON object with keys: type, place_name, place_phone, date, time, name, contact, confirmation_id.

Keep replies SHORT - one to three sentences. This is spoken aloud, so avoid lists, headers, or markdown. Sound like a helpful person, not a form.
"""

TOOLS = [
    search_nearby_places,
    list_available_slots,
    check_availability,
    search_flights,
    book_appointment,
]


def build_model():
    """Create the model per request so it always knows today's date."""
    today = date_cls.today().strftime("%A, %B %d, %Y")
    instruction = (
        SYSTEM_PROMPT
        + f"\nToday's date is {today}. When calling tools, convert words like "
        + "'tomorrow' or 'Friday' into real calendar dates (YYYY-MM-DD).\n"
    )
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=instruction,
        tools=TOOLS,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = (data or {}).get("message", "").strip()
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    sid = session["sid"]
    history = CONVERSATIONS.setdefault(sid, [])

    try:
        chat_session = build_model().start_chat(
            history=history, enable_automatic_function_calling=True
        )
        response = chat_session.send_message(user_message)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

    reply_text = response.text.strip()
    CONVERSATIONS[sid] = chat_session.history

    booking = None
    spoken_reply = reply_text
    marker = "BOOKING_CONFIRMED:"
    if marker in reply_text:
        spoken_reply, _, raw_json = reply_text.partition(marker)
        spoken_reply = spoken_reply.strip()
        try:
            booking = json.loads(raw_json.strip())
        except json.JSONDecodeError:
            booking = {"raw": raw_json.strip()}

    return jsonify({"reply": spoken_reply, "booking": booking})


@app.route("/api/reset", methods=["POST"])
def reset():
    sid = session.get("sid")
    if sid and sid in CONVERSATIONS:
        del CONVERSATIONS[sid]
    return jsonify({"ok": True})


@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/api/bookings", methods=["GET"])
def list_bookings():
    """See everything actually booked so far - handy for demoing the app."""
    with _bookings_lock:
        return jsonify(_load_bookings())


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
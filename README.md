# Voice Booking Assistant

A voice agent that books anything - a doctor's appointment, a flight, a
table, a haircut - by talking it through with you. Runs as a local web app,
so it works in any browser on your laptop or phone (same wifi network).

## How it works

- **Speech-to-text & text-to-speech**: done entirely in the browser with
  the built-in Web Speech API. No extra API keys or cost for this part.
  Works in Chrome, Edge, and Safari. (Firefox doesn't support
  `SpeechRecognition` yet.)
- **Conversation logic**: each time you speak, the transcript is sent to
  the Flask backend, which calls the Google Gemini API to figure out what
  to ask next and keeps track of the conversation. The call is continuous -
  tap the mic once to start, and it keeps listening and responding
  automatically until you end the call.
- **Real place search**: for anything that needs a physical location (a
  pediatrician, dentist, salon, etc.), Gemini can call a search_nearby_places
  tool that queries the Google Places API for real nearby businesses - name,
  address, phone number, and rating - and reads back a couple of options.
- **Flight search**: uses the Duffel API (test/sandbox mode) to search
  flight options between two places - airline, times, stops, and price.
  Sandbox mode returns sample data, not real flights or live prices.
- **Booking confirmation**: once Gemini has everything it needs (place
  chosen, preferred date/time, name, contact info), it calls a tool that
  actually reserves the slot in this app's own appointment book (stored in
  bookings.json) and returns a real confirmation ID. Trying to book an
  already-taken slot is correctly rejected.
- **Anti-hallucination guardrail**: the system prompt explicitly forbids
  stating any business name, address, phone number, airline, or price that
  didn't come from an actual tool result - this was added after testing
  surfaced the model inventing plausible-sounding but fake details.

## Important limitation: no real-time appointment availability

No public API exposes a clinic's or restaurant's actual open appointment
slots - that data lives inside each business's private scheduling software.
Even commercial services like Zocdoc or OpenTable only show real slots
because they've struck individual data-sharing deals with each business.
So this assistant finds real nearby places and notes your preferred time,
but you still need to call the business yourself to confirm an actual slot.
The assistant tells the caller this explicitly at the end of each booking.

## Setup

1. Install dependencies:

   pip install -r requirements.txt

2. Get a Gemini API key from Google AI Studio (aistudio.google.com/app/apikey).

3. Get a separate Google API key with Places API (Legacy) enabled at
   console.cloud.google.com/apis/library/places-backend.googleapis.com
   (a Gemini key created via AI Studio is bound to a service account and
   cannot also access Places API - these need to be two different keys).

4. Get a free Duffel test token from Duffel (app.duffel.com) under
   Developers -> Access tokens (starts with duffel_test_).

5. Set all three as environment variables. On Windows, open a fresh
   PowerShell window and run:

   setx GOOGLE_API_KEY "your-gemini-key"
   setx PLACES_API_KEY "your-places-key"
   setx DUFFEL_API_KEY "your-duffel-test-token"

   Then fully close and reopen your terminal/editor so it picks up the
   new variables.

6. Run the app:

   python app.py

7. Open http://localhost:5000 in Chrome or Safari.

## Project structure

app.py                 Flask app: routes, conversation logic, appointment book
flights.py              Duffel flight search tool
templates/index.html     The voice agent UI (mic, transcript, booking card)
templates/history.html    View all past bookings
static/style.css        Styling

## Roadmap / future work

- Google Calendar sync: adding a confirmed booking as a real event on
  the caller's own Google Calendar (requires OAuth sign-in, in progress).
- Real phone calls to the business: the agent actually calling a clinic
  or restaurant to book a real slot with a human, instead of just handing
  over their number. Would need a telephony provider (Twilio), a realtime
  speech pipeline, and - importantly - compliance with AI-call disclosure
  laws, which vary by jurisdiction and must be built in from the start.

## Portfolio note

This project touches conversational state management, LLM tool/function
calling, a self-built scheduling system with conflict detection, two
external data APIs (Google Places, Duffel), and a real-time browser API -
while staying small enough to explain in an interview. It also includes a
concrete, fixed example of an AI hallucination bug, which is a useful
story for discussing LLM engineering judgment.

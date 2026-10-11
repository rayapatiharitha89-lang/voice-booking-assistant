\# Voice Booking Assistant



A voice agent that books anything - a doctor's appointment, a flight, a

table, a haircut - by talking it through with you. Runs as a local web app,

so it works in any browser on your laptop or phone (same wifi network).



\## How it works



\- \*\*Speech-to-text \& text-to-speech\*\*: done entirely in the browser with

&#x20; the built-in Web Speech API. No extra API keys or cost for this part.

&#x20; Works in Chrome, Edge, and Safari. (Firefox doesn't support

&#x20; `SpeechRecognition` yet.)

\- \*\*Conversation logic\*\*: each time you speak, the transcript is sent to

&#x20; the Flask backend, which calls the Google Gemini API to figure out what

&#x20; to ask next and keeps track of the conversation. The call is continuous -

&#x20; tap the mic once to start, and it keeps listening and responding

&#x20; automatically until you end the call.

\- \*\*Real place search\*\*: for anything that needs a physical location (a

&#x20; pediatrician, dentist, salon, etc.), Gemini can call a `search\_nearby\_places`

&#x20; tool that queries the Google Places API for real nearby businesses - name,

&#x20; address, phone number, and rating - and reads back a couple of options.

\- \*\*Flight search\*\*: uses the Duffel API (test/sandbox mode) to search

&#x20; flight options between two places - airline, times, stops, and price.

&#x20; Sandbox mode returns sample data, not real flights or live prices.

\- \*\*Booking confirmation\*\*: once Gemini has everything it needs (place

&#x20; chosen, preferred date/time, name, contact info), it calls a tool that

&#x20; actually reserves the slot in this app's own appointment book (stored in

&#x20; `bookings.json`) and returns a real confirmation ID. Trying to book an

&#x20; already-taken slot is correctly rejected.

\- \*\*Anti-hallucination guardrail\*\*: the system prompt explicitly forbids

&#x20; stating any business name, address, phone number, airline, or price that

&#x20; didn't come from an actual tool result - this was added after testing

&#x20; surfaced the model inventing plausible-sounding but fake details.



\## Important limitation: no real-time appointment availability



No public API exposes a clinic's or restaurant's actual open appointment

slots - that data lives inside each business's private scheduling software.

Even commercial services like Zocdoc or OpenTable only show real slots

because they've struck individual data-sharing deals with each business.

So this assistant finds real nearby places and notes your \*preferred\* time,

but you still need to call the business yourself to confirm an actual slot.

The assistant tells the caller this explicitly at the end of each booking.



\## Setup



1\. Install dependencies:

```bash

&#x20;  pip install -r requirements.txt

```



2\. Get a Gemini API key from \[Google AI Studio](https://aistudio.google.com/app/apikey).



3\. Get a separate Google API key with \*\*Places API (Legacy)\*\* enabled at

&#x20;  https://console.cloud.google.com/apis/library/places-backend.googleapis.com

&#x20;  (a Gemini key created via AI Studio is bound to a service account and

&#x20;  cannot also access Places API - these need to be two different keys).



4\. Get a free Duffel test token from \[Duffel](https://app.duffel.com) under

&#x20;  Developers → Access tokens (starts with `duffel\_test\_`).



5\. Set all three as environment variables. On Windows, open a fresh

&#x20;  PowerShell window and run:

```powershell

&#x20;  setx GOOGLE\_API\_KEY "your-gemini-key"

&#x20;  setx PLACES\_API\_KEY "your-places-key"

&#x20;  setx DUFFEL\_API\_KEY "your-duffel-test-token"

```

&#x20;  Then fully close and reopen your terminal/editor so it picks up the

&#x20;  new variables.



6\. Run the app:

```bash

&#x20;  python app.py

```



7\. Open `http://localhost:5000` in Chrome or Safari.



\## Project structure


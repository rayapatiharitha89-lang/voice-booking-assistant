"""
Flight search using the Duffel API.
"""
import os
from datetime import datetime

import requests

DUFFEL_API_KEY = os.environ.get("DUFFEL_API_KEY", "")
BASE_URL = "https://api.duffel.com"


def _headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Duffel-Version": "v2",
        "Authorization": f"Bearer {DUFFEL_API_KEY}",
    }


def _place_code(query):
    resp = requests.get(
        f"{BASE_URL}/places/suggestions",
        params={"query": query},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    places = resp.json().get("data", [])
    if not places:
        return None, None
    return places[0].get("iata_code"), places[0].get("name")


def _fmt_time(iso_text):
    try:
        return datetime.fromisoformat(iso_text).strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return str(iso_text)


def search_flights(origin: str, destination: str, departure_date: str) -> str:
    """Search for flight options between two places on one date. Use this
    for ANY flight booking, instead of the appointment slot tools. origin
    and destination are city or airport names as the caller said them.
    departure_date must be YYYY-MM-DD. Returns up to 3 cheapest options.
    """
    if not DUFFEL_API_KEY:
        return "Flight search is not set up on this system. Tell the caller you cannot look up flights right now."

    try:
        origin_code, origin_name = _place_code(origin)
        dest_code, dest_name = _place_code(destination)
        if not origin_code or not dest_code:
            return "Could not match one of those places to an airport or city. Ask the caller to repeat the city names."

        resp = requests.post(
            f"{BASE_URL}/air/offer_requests",
            params={"return_offers": "true", "supplier_timeout": "10000"},
            headers=_headers(),
            json={
                "data": {
                    "slices": [{"origin": origin_code, "destination": dest_code, "departure_date": departure_date}],
                    "passengers": [{"type": "adult"}],
                    "cabin_class": "economy",
                }
            },
            timeout=30,
        )
        resp.raise_for_status()
        offers = resp.json().get("data", {}).get("offers", [])
    except Exception as exc:
        print("search_flights error:", exc)
        return "Flight search failed. Tell the caller you could not look up flights right now."

    is_test = DUFFEL_API_KEY.startswith("duffel_test_")
    header = f"{origin_name} ({origin_code}) to {dest_name} ({dest_code}) on {departure_date}."

    if not offers:
        note = " This is a test environment with limited coverage." if is_test else ""
        return f"No flight options found. {header}{note}"

    offers.sort(key=lambda o: float(o.get("total_amount", "0") or 0))
    lines = []
    for offer in offers:
        if len(lines) == 3:
            break
        slices = offer.get("slices") or [{}]
        segments = slices[0].get("segments") or []
        if not segments:
            continue
        number = len(lines) + 1
        airline = offer.get("owner", {}).get("name", "Unknown airline")
        departs = _fmt_time(segments[0].get("departing_at"))
        arrives = _fmt_time(segments[-1].get("arriving_at"))
        stops = len(segments) - 1
        stops_text = "nonstop" if stops == 0 else f"{stops} stop" + ("s" if stops > 1 else "")
        price = f"{offer.get('total_amount')} {offer.get('total_currency')}"
        lines.append(f"{number}) {airline}, departs {departs}, arrives {arrives}, {stops_text}, {price}")

    prefix = "TEST DATA from a sandbox - these are NOT real flights or prices; tell the caller this. " if is_test else ""
    return f"{prefix}{header} Options: " + "; ".join(lines)

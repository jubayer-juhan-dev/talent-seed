"""Location normalization for talent profiles.

GitHub locations are free text: "Berlin", "🇨🇭", "Earth", "127.0.0.1".
This module turns them into (display, country) or (None, None) for junk.

- flag emoji  -> country name (decoded from regional indicators + ISO map)
- junk        -> (None, None): Earth, Remote, Internet, Web3, IPs, ...
- city        -> country via a curated city map (data-driven, extendable)
- "City, X"   -> X is the country (or a US state -> United States)
"""

import re

ISO_COUNTRY = {
    "AD": "Andorra", "AE": "United Arab Emirates", "AF": "Afghanistan",
    "AG": "Antigua and Barbuda", "AL": "Albania", "AM": "Armenia",
    "AO": "Angola", "AR": "Argentina", "AT": "Austria", "AU": "Australia",
    "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BB": "Barbados",
    "BD": "Bangladesh", "BE": "Belgium", "BF": "Burkina Faso",
    "BG": "Bulgaria", "BH": "Bahrain", "BI": "Burundi", "BJ": "Benin",
    "BM": "Bermuda", "BN": "Brunei", "BO": "Bolivia", "BR": "Brazil",
    "BS": "Bahamas", "BT": "Bhutan", "BW": "Botswana", "BY": "Belarus",
    "BZ": "Belize", "CA": "Canada", "CD": "DR Congo", "CF": "Central African Republic",
    "CG": "Congo", "CH": "Switzerland", "CI": "Ivory Coast", "CL": "Chile",
    "CM": "Cameroon", "CN": "China", "CO": "Colombia", "CR": "Costa Rica",
    "CU": "Cuba", "CV": "Cabo Verde", "CY": "Cyprus", "CZ": "Czechia",
    "DE": "Germany", "DJ": "Djibouti", "DK": "Denmark", "DM": "Dominica",
    "DO": "Dominican Republic", "DZ": "Algeria", "EC": "Ecuador",
    "EE": "Estonia", "EG": "Egypt", "ER": "Eritrea", "ES": "Spain",
    "ET": "Ethiopia", "FI": "Finland", "FJ": "Fiji", "FO": "Faroe Islands",
    "FR": "France", "GA": "Gabon", "GB": "United Kingdom", "GD": "Grenada",
    "GE": "Georgia", "GF": "French Guiana", "GG": "Guernsey", "GH": "Ghana",
    "GI": "Gibraltar", "GL": "Greenland", "GM": "Gambia", "GN": "Guinea",
    "GP": "Guadeloupe", "GR": "Greece", "GT": "Guatemala", "GU": "Guam",
    "GW": "Guinea-Bissau", "GY": "Guyana", "HK": "Hong Kong", "HN": "Honduras",
    "HR": "Croatia", "HT": "Haiti", "HU": "Hungary", "ID": "Indonesia",
    "IE": "Ireland", "IL": "Israel", "IM": "Isle of Man", "IN": "India",
    "IQ": "Iraq", "IR": "Iran", "IS": "Iceland", "IT": "Italy",
    "JE": "Jersey", "JM": "Jamaica", "JO": "Jordan", "JP": "Japan",
    "KE": "Kenya", "KG": "Kyrgyzstan", "KH": "Cambodia", "KI": "Kiribati",
    "KN": "Saint Kitts and Nevis", "KP": "North Korea", "KR": "South Korea",
    "KW": "Kuwait", "KY": "Cayman Islands", "KZ": "Kazakhstan", "LA": "Laos",
    "LB": "Lebanon", "LC": "Saint Lucia", "LI": "Liechtenstein",
    "LK": "Sri Lanka", "LR": "Liberia", "LS": "Lesotho", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "LY": "Libya", "MA": "Morocco",
    "MC": "Monaco", "MD": "Moldova", "ME": "Montenegro", "MG": "Madagascar",
    "MH": "Marshall Islands", "MK": "North Macedonia", "ML": "Mali",
    "MM": "Myanmar", "MN": "Mongolia", "MO": "Macao", "MQ": "Martinique",
    "MR": "Mauritania", "MT": "Malta", "MU": "Mauritius", "MV": "Maldives",
    "MW": "Malawi", "MX": "Mexico", "MY": "Malaysia", "MZ": "Mozambique",
    "NA": "Namibia", "NC": "New Caledonia", "NE": "Niger", "NG": "Nigeria",
    "NI": "Nicaragua", "NL": "Netherlands", "NO": "Norway", "NP": "Nepal",
    "NR": "Nauru", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama",
    "PE": "Peru", "PF": "French Polynesia", "PG": "Papua New Guinea",
    "PH": "Philippines", "PK": "Pakistan", "PL": "Poland", "PR": "Puerto Rico",
    "PS": "Palestine", "PT": "Portugal", "PY": "Paraguay", "QA": "Qatar",
    "RE": "Reunion", "RO": "Romania", "RS": "Serbia", "RU": "Russia",
    "RW": "Rwanda", "SA": "Saudi Arabia", "SB": "Solomon Islands",
    "SC": "Seychelles", "SD": "Sudan", "SE": "Sweden", "SG": "Singapore",
    "SI": "Slovenia", "SK": "Slovakia", "SL": "Sierra Leone", "SM": "San Marino",
    "SN": "Senegal", "SO": "Somalia", "SR": "Suriname", "SS": "South Sudan",
    "ST": "Sao Tome and Principe", "SV": "El Salvador", "SY": "Syria",
    "SZ": "Eswatini", "TC": "Turks and Caicos", "TD": "Chad",
    "TF": "French Southern Territories", "TG": "Togo", "TH": "Thailand",
    "TJ": "Tajikistan", "TL": "Timor-Leste", "TM": "Turkmenistan",
    "TN": "Tunisia", "TO": "Tonga", "TR": "Turkey", "TT": "Trinidad and Tobago",
    "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraine", "UG": "Uganda",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
    "VA": "Vatican City", "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela", "VG": "British Virgin Islands", "VI": "U.S. Virgin Islands",
    "VN": "Vietnam", "VU": "Vanuatu", "WS": "Samoa", "XK": "Kosovo",
    "YE": "Yemen", "ZA": "South Africa", "ZM": "Zambia", "ZW": "Zimbabwe",
}

COUNTRY_ALIASES = {
    "uk": "United Kingdom", "u.k.": "United Kingdom",
    "great britain": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom",
    "britain": "United Kingdom",
    "usa": "United States", "u.s.a.": "United States",
    "u.s.": "United States", "us": "United States",
    "united states of america": "United States", "america": "United States",
    "uae": "United Arab Emirates", "emirates": "United Arab Emirates",
    "korea": "South Korea", "republic of korea": "South Korea",
    "viet nam": "Vietnam", "russian federation": "Russia",
    "czech republic": "Czechia", "holland": "Netherlands",
    "turkiye": "Turkey", "türkiye": "Turkey",
}

COUNTRIES = set(ISO_COUNTRY.values()) | {
    "United Kingdom", "United States", "United Arab Emirates", "South Korea",
    "North Korea", "Czechia", "Hong Kong", "Taiwan", "Palestine", "Kosovo",
    "DR Congo", "Congo", "Ivory Coast",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
}

CITY_COUNTRY = {
    "berlin": "Germany", "munich": "Germany", "hamburg": "Germany",
    "cologne": "Germany", "frankfurt": "Germany", "stuttgart": "Germany",
    "düsseldorf": "Germany", "dusseldorf": "Germany", "leipzig": "Germany",
    "dortmund": "Germany", "essen": "Germany", "bremen": "Germany",
    "hanover": "Germany", "dresden": "Germany", "freiburg": "Germany",
    "london": "United Kingdom", "manchester": "United Kingdom",
    "birmingham": "United Kingdom", "edinburgh": "United Kingdom",
    "glasgow": "United Kingdom", "bristol": "United Kingdom",
    "leeds": "United Kingdom", "liverpool": "United Kingdom",
    "cambridge": "United Kingdom", "oxford": "United Kingdom",
    "paris": "France", "lyon": "France", "marseille": "France",
    "toulouse": "France", "nantes": "France", "bordeaux": "France",
    "lille": "France", "nice": "France", "montpellier": "France",
    "zurich": "Switzerland", "zürich": "Switzerland", "geneva": "Switzerland",
    "bern": "Switzerland", "basel": "Switzerland", "lausanne": "Switzerland",
    "zug": "Switzerland", "lucerne": "Switzerland",
    "amsterdam": "Netherlands", "rotterdam": "Netherlands",
    "utrecht": "Netherlands", "eindhoven": "Netherlands",
    "the hague": "Netherlands", "den haag": "Netherlands",
    "madrid": "Spain", "barcelona": "Spain", "valencia": "Spain",
    "seville": "Spain", "malaga": "Spain", "málaga": "Spain",
    "bilbao": "Spain", "granada": "Spain", "alicante": "Spain",
    "lisbon": "Portugal", "porto": "Portugal", "braga": "Portugal",
    "rome": "Italy", "milan": "Italy", "naples": "Italy", "turin": "Italy",
    "bologna": "Italy", "florence": "Italy", "venice": "Italy",
    "vienna": "Austria", "salzburg": "Austria", "graz": "Austria",
    "innsbruck": "Austria", "linz": "Austria",
    "warsaw": "Poland", "krakow": "Poland", "kraków": "Poland",
    "wroclaw": "Poland", "wrocław": "Poland", "gdansk": "Poland",
    "gdańsk": "Poland", "poznan": "Poland", "poznań": "Poland",
    "lodz": "Poland", "łódź": "Poland",
    "prague": "Czechia", "brno": "Czechia",
    "budapest": "Hungary", "debrecen": "Hungary",
    "bucharest": "Romania", "cluj": "Romania", "cluj-napoca": "Romania",
    "timisoara": "Romania", "timișoara": "Romania", "iasi": "Romania",
    "sofia": "Bulgaria", "plovdiv": "Bulgaria", "varna": "Bulgaria",
    "belgrade": "Serbia", "novi sad": "Serbia",
    "zagreb": "Croatia", "split": "Croatia",
    "ljubljana": "Slovenia", "bratislava": "Slovakia",
    "athens": "Greece", "thessaloniki": "Greece",
    "stockholm": "Sweden", "gothenburg": "Sweden", "malmo": "Sweden",
    "malmö": "Sweden", "uppsala": "Sweden",
    "oslo": "Norway", "bergen": "Norway", "trondheim": "Norway",
    "copenhagen": "Denmark", "aarhus": "Denmark", "odense": "Denmark",
    "helsinki": "Finland", "tampere": "Finland", "espoo": "Finland",
    "tallinn": "Estonia", "tartu": "Estonia",
    "riga": "Latvia", "vilnius": "Lithuania", "kaunas": "Lithuania",
    "dublin": "Ireland", "cork": "Ireland", "galway": "Ireland",
    "reykjavik": "Iceland", "reykjavík": "Iceland",
    "kyiv": "Ukraine", "kiev": "Ukraine", "lviv": "Ukraine",
    "kharkiv": "Ukraine", "odesa": "Ukraine", "dnipro": "Ukraine",
    "minsk": "Belarus", "chisinau": "Moldova", "chișinău": "Moldova",
    "tbilisi": "Georgia", "yerevan": "Armenia", "baku": "Azerbaijan",
    "istanbul": "Turkey", "ankara": "Turkey", "izmir": "Turkey",
    "antalya": "Turkey",
    "moscow": "Russia", "saint petersburg": "Russia",
    "st. petersburg": "Russia", "novosibirsk": "Russia", "kazan": "Russia",
    "yekaterinburg": "Russia",
    "tokyo": "Japan", "osaka": "Japan", "kyoto": "Japan",
    "nagoya": "Japan", "fukuoka": "Japan", "sapporo": "Japan",
    "beijing": "China", "shanghai": "China", "shenzhen": "China",
    "hangzhou": "China", "guangzhou": "China", "chengdu": "China",
    "nanjing": "China", "wuhan": "China", "xian": "China", "xi'an": "China",
    "seoul": "South Korea", "busan": "South Korea", "incheon": "South Korea",
    "taipei": "Taiwan", "hsinchu": "Taiwan", "taichung": "Taiwan",
    "hong kong": "Hong Kong",
    "bangalore": "India", "bengaluru": "India", "mumbai": "India",
    "delhi": "India", "new delhi": "India", "hyderabad": "India",
    "chennai": "India", "pune": "India", "kolkata": "India",
    "ahmedabad": "India", "jaipur": "India", "kochi": "India",
    "indore": "India", "surat": "India", "lucknow": "India",
    "karachi": "Pakistan", "lahore": "Pakistan", "islamabad": "Pakistan",
    "dhaka": "Bangladesh", "chattogram": "Bangladesh",
    "chittagong": "Bangladesh", "sylhet": "Bangladesh",
    "kathmandu": "Nepal", "colombo": "Sri Lanka",
    "singapore": "Singapore",
    "jakarta": "Indonesia", "bali": "Indonesia", "bandung": "Indonesia",
    "surabaya": "Indonesia", "denpasar": "Indonesia",
    "kuala lumpur": "Malaysia", "penang": "Malaysia",
    "bangkok": "Thailand", "chiang mai": "Thailand", "phuket": "Thailand",
    "hanoi": "Vietnam", "ho chi minh city": "Vietnam", "saigon": "Vietnam",
    "da nang": "Vietnam",
    "manila": "Philippines", "cebu": "Philippines", "davao": "Philippines",
    "sydney": "Australia", "melbourne": "Australia", "brisbane": "Australia",
    "perth": "Australia", "adelaide": "Australia", "canberra": "Australia",
    "hobart": "Australia", "darwin": "Australia", "gold coast": "Australia",
    "auckland": "New Zealand", "wellington": "New Zealand",
    "christchurch": "New Zealand",
    "toronto": "Canada", "vancouver": "Canada", "montreal": "Canada",
    "montréal": "Canada", "calgary": "Canada", "ottawa": "Canada",
    "edmonton": "Canada", "winnipeg": "Canada", "waterloo": "Canada",
    "kitchener": "Canada", "quebec city": "Canada",
    "new york": "United States", "new york city": "United States",
    "nyc": "United States", "san francisco": "United States",
    "sf": "United States", "los angeles": "United States",
    "la": "United States", "seattle": "United States",
    "austin": "United States", "boston": "United States",
    "chicago": "United States", "denver": "United States",
    "portland": "United States", "san diego": "United States",
    "san jose": "United States", "houston": "United States",
    "dallas": "United States", "atlanta": "United States",
    "miami": "United States", "phoenix": "United States",
    "philadelphia": "United States", "nashville": "United States",
    "las vegas": "United States", "salt lake city": "United States",
    "raleigh": "United States", "charlotte": "United States",
    "detroit": "United States", "minneapolis": "United States",
    "pittsburgh": "United States", "cleveland": "United States",
    "cincinnati": "United States", "columbus": "United States",
    "indianapolis": "United States", "kansas city": "United States",
    "st. louis": "United States", "saint louis": "United States",
    "sacramento": "United States", "fresno": "United States",
    "tucson": "United States", "albuquerque": "United States",
    "omaha": "United States", "tulsa": "United States",
    "american fork": "United States", "palo alto": "United States",
    "mountain view": "United States", "sunnyvale": "United States",
    "cupertino": "United States", "redmond": "United States",
    "bellevue": "United States", "boulder": "United States",
    "ann arbor": "United States", "madison": "United States",
    "san francisco bay area": "United States", "bay area": "United States",
    "silicon valley": "United States",
    "mexico city": "Mexico", "guadalajara": "Mexico",
    "monterrey": "Mexico", "cancun": "Mexico", "cancún": "Mexico",
    "buenos aires": "Argentina", "cordoba": "Argentina",
    "córdoba": "Argentina", "rosario": "Argentina", "mendoza": "Argentina",
    "são paulo": "Brazil", "sao paulo": "Brazil",
    "rio de janeiro": "Brazil", "brasilia": "Brazil",
    "brasília": "Brazil", "belo horizonte": "Brazil",
    "curitiba": "Brazil", "florianopolis": "Brazil",
    "florianópolis": "Brazil", "porto alegre": "Brazil",
    "salvador": "Brazil", "recife": "Brazil", "fortaleza": "Brazil",
    "santiago": "Chile", "valparaiso": "Chile", "valparaíso": "Chile",
    "bogota": "Colombia", "bogotá": "Colombia", "medellin": "Colombia",
    "medellín": "Colombia", "cali": "Colombia",
    "lima": "Peru", "quito": "Ecuador", "guayaquil": "Ecuador",
    "caracas": "Venezuela", "montevideo": "Uruguay",
    "asuncion": "Paraguay", "asunción": "Paraguay",
    "la paz": "Bolivia", "sucre": "Bolivia",
    "lagos": "Nigeria", "abuja": "Nigeria", "ibadan": "Nigeria",
    "nairobi": "Kenya", "mombasa": "Kenya",
    "cape town": "South Africa", "johannesburg": "South Africa",
    "pretoria": "South Africa", "durban": "South Africa",
    "accra": "Ghana", "kumasi": "Ghana",
    "cairo": "Egypt", "alexandria": "Egypt", "giza": "Egypt",
    "casablanca": "Morocco", "rabat": "Morocco", "marrakech": "Morocco",
    "tunis": "Tunisia", "algiers": "Algeria",
    "addis ababa": "Ethiopia", "dar es salaam": "Tanzania",
    "kampala": "Uganda", "kigali": "Rwanda", "lusaka": "Zambia",
    "harare": "Zimbabwe", "maputo": "Mozambique", "luanda": "Angola",
    "dakar": "Senegal", "abidjan": "Ivory Coast",
    "tel aviv": "Israel", "jerusalem": "Israel", "haifa": "Israel",
    "dubai": "United Arab Emirates", "abu dhabi": "United Arab Emirates",
    "sharjah": "United Arab Emirates",
    "doha": "Qatar", "riyadh": "Saudi Arabia", "jeddah": "Saudi Arabia",
    "muscat": "Oman", "kuwait city": "Kuwait", "manama": "Bahrain",
    "amman": "Jordan", "beirut": "Lebanon", "tehran": "Iran",
    "baghdad": "Iraq", "tashkent": "Uzbekistan", "almaty": "Kazakhstan",
    "bishkek": "Kyrgyzstan", "ulaanbaatar": "Mongolia",
}

JUNK = {
    "earth", "remote", "worldwide", "global", "everywhere", "anywhere",
    "internet", "online", "the internet", "web", "web3", "crypto",
    "blockchain", "metaverse", "moon", "the moon", "mars", "space",
    "127.0.0.1", "localhost", "0.0.0.0", "home", "nomad", "digital nomad",
    "distributed", "decentralized", "virtual", "cloud", "cyberspace",
    "world", "planet earth", "remote worldwide", "remote / worldwide",
    "remote-first", "fully remote", "work from home", "wfh", "n/a", "na",
    "none", "unknown", "-", "—", "here", "there", "somewhere",
    "your heart", "ethereum", "bitcoin", "solana", "defi",
}

REGION_COUNTRY = {
    "europe": None, "eu": None, "european union": None,
    "asia": None, "africa": None, "north america": None,
    "south america": None, "latin america": None, "latam": None,
    "middle east": None, "mena": None, "scandinavia": None,
    "balkans": None, "caribbean": None, "oceania": None,
    "uk & ireland": None, "dach": None,
}

_FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def _flag_country(text):
    """First flag emoji in text -> country name, or None."""
    m = _FLAG_RE.search(text)
    if not m:
        return None
    chars = [c for c in m.group(0)]
    if len(chars) != 2:
        return None
    code = "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in chars)
    return ISO_COUNTRY.get(code)


def normalize_country_of(part):
    """One comma-part -> country name or None."""
    p = part.strip()
    if not p:
        return None
    low = p.lower()
    if low in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[low]
    if p in COUNTRIES:
        return p
    if low in CITY_COUNTRY:
        return CITY_COUNTRY[low]
    if p in US_STATES:
        return "United States"
    return None


def normalize(location):
    """Free-text location -> (display, country) or (None, None) for junk.

    display keeps the city when known: "Berlin, Germany". country is the
    canonical country name for filtering, or None when it cannot be pinned.
    """
    if not location:
        return None, None
    raw = str(location).strip()
    if not raw:
        return None, None
    low = raw.lower().strip(" .,")
    if low in JUNK:
        return None, None
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", raw):
        return None, None

    # flag emoji anywhere -> that country wins
    flag = _flag_country(raw)
    if flag:
        rest = _FLAG_RE.sub("", raw).strip(" ,·-")
        if rest and rest.lower() not in JUNK and normalize_country_of(rest) in (None, flag):
            city = rest.split(",")[0].strip()
            if city and city.lower() != flag.lower():
                return f"{city}, {flag}", flag
        return flag, flag

    parts = [p.strip() for p in re.split(r"[,/|]", raw) if p.strip()]
    parts = [p for p in parts if p.lower() not in JUNK]
    if not parts:
        return None, None

    # find the country: scan parts from the end (country usually last)
    country = None
    country_idx = None
    for i in range(len(parts) - 1, -1, -1):
        c = normalize_country_of(parts[i])
        if c:
            country, country_idx = c, i
            break
    if country is None and len(parts) == 1 and low in REGION_COUNTRY:
        return None, None

    if country is None:
        # single unknown token: keep as display, no country
        if len(parts) == 1:
            return parts[0], None
        return ", ".join(parts), None

    city = None
    for i, p in enumerate(parts):
        if i != country_idx and p.lower() not in JUNK:
            city = p
            break
    if city is None and parts[country_idx].lower() in CITY_COUNTRY:
        # the location was a bare city ("Berlin") -> keep it in the display
        city = parts[country_idx]
    if city and city.lower() != country.lower():
        return f"{city}, {country}", country
    return country, country

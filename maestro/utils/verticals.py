from __future__ import annotations

_VERTICALS: dict[str, list[str]] = {
    # HOA / property management
    "hoa": ["HOA", "homeowners association", "condominium association", "condo association"],
    "hoas": ["HOA", "homeowners association", "condominium association", "condo association"],
    "homeowners association": ["HOA", "homeowners association", "condominium association", "condo association"],
    "condo": ["condominium", "condo association", "HOA", "apartment complex"],
    "condominium": ["condominium", "condo association", "HOA", "apartment complex"],
    "property manager": ["property management company", "property manager", "real estate management"],
    "property management": ["property management company", "property manager", "real estate management"],
    # Hospitality
    "hotel": ["hotel", "motel", "inn", "boutique hotel"],
    "motel": ["motel", "hotel", "inn"],
    "resort": ["resort", "hotel", "inn", "vacation resort"],
    "bed and breakfast": ["bed and breakfast", "B&B", "inn", "guesthouse"],
    "inn": ["inn", "bed and breakfast", "B&B", "boutique hotel"],
    # Marine
    "marina": ["marina", "boat yard", "yacht club", "boatyard", "boat storage", "boat club", "sailing club"],
    "yacht club": ["yacht club", "marina", "sailing club", "boating club", "boat club"],
    # Education
    "school": ["private school", "independent school", "academy", "prep school", "day school", "K-12 school", "charter school", "Montessori"],
    "day care": ["day care", "daycare", "child care", "preschool", "early education center"],
    "daycare": ["daycare", "day care", "child care", "preschool", "early education center"],
    "preschool": ["preschool", "day care", "early childhood education", "nursery school", "Montessori"],
    # Healthcare
    "hospital": ["hospital", "medical center", "health system", "medical facility", "outpatient clinic"],
    "hospice": ["hospice", "palliative care", "home health agency", "hospice care", "end of life care"],
    "senior living": ["senior living", "assisted living", "nursing home", "retirement community", "memory care", "continuing care"],
    "assisted living": ["assisted living", "senior living", "nursing home", "retirement community", "memory care"],
    "nursing home": ["nursing home", "skilled nursing facility", "senior living", "assisted living", "rehabilitation center"],
    "senior center": ["senior center", "adult day program", "council on aging", "elder services"],
    "adult day": ["adult day program", "senior center", "elder day services", "day health program"],
    # Food & Beverage
    "restaurant": ["restaurant", "cafe", "eatery", "bistro", "diner"],
    "brewery": ["brewery", "craft brewery", "taproom", "beer garden"],
    "winery": ["winery", "vineyard", "wine bar"],
    # Recreation & Fitness
    "gym": ["gym", "fitness center", "health club", "CrossFit", "yoga studio"],
    "spa": ["spa", "wellness center", "massage therapy", "day spa"],
    "golf": ["golf course", "country club", "golf club"],
    "country club": ["country club", "golf club", "private club"],
    "campground": ["campground", "RV park", "camping resort"],
    # Events
    "wedding venue": ["wedding venue", "event venue", "banquet hall", "function hall"],
    "event venue": ["event venue", "banquet hall", "function hall", "conference center"],
    # Commercial
    "office park": ["office park", "business park", "corporate campus", "commercial complex"],
    "gas station": ["gas station", "fuel station", "service station"],
    "real estate developer": ["real estate developer", "property developer", "real estate company"],
    # Faith & Community
    "church": ["church", "parish", "congregation"],
    # Facilities
    "facility": ["facility", "commercial property", "institutional facility"],
    # Cape Cod / seasonal specifics
    "campground": ["campground", "RV park", "camping resort", "camp site", "glamping"],
    "wedding venue": ["wedding venue", "event venue", "banquet hall", "function hall", "event space"],
    "vacation rental": ["vacation rental", "property management", "rental company", "cottage rentals"],
    "landscape": ["landscape company", "landscaping", "lawn care", "grounds maintenance", "lawn service"],
}


def expand_target(target: str) -> list[str]:
    """Return search keyword variants for a vertical target.

    Falls back to [target] when the vertical is not mapped.
    """
    return _VERTICALS.get(target.strip().casefold(), [target.strip()])

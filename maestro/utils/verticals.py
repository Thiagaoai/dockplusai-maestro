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
    "marina": ["marina", "boat yard", "yacht club", "boatyard", "boat storage"],
    "yacht club": ["yacht club", "marina", "sailing club", "boating club"],
    # Education
    "school": ["school", "K-12", "private school", "academy", "elementary school"],
    "day care": ["day care", "daycare", "child care", "preschool", "early education"],
    "daycare": ["daycare", "day care", "child care", "preschool", "early education"],
    "preschool": ["preschool", "day care", "early education", "nursery school"],
    # Healthcare
    "hospital": ["hospital", "medical center", "health system", "medical facility"],
    "hospice": ["hospice", "palliative care", "home health agency", "hospice care"],
    "senior living": ["senior living", "assisted living", "nursing home", "retirement community", "memory care"],
    "assisted living": ["assisted living", "senior living", "nursing home", "retirement community"],
    "nursing home": ["nursing home", "skilled nursing facility", "senior living", "assisted living"],
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
}


def expand_target(target: str) -> list[str]:
    """Return search keyword variants for a vertical target.

    Falls back to [target] when the vertical is not mapped.
    """
    return _VERTICALS.get(target.strip().casefold(), [target.strip()])

from pydantic import BaseModel, Field


class Contact(BaseModel):
    phone: str
    email: str
    address: str | None = None
    website: str | None = None


class Tone(BaseModel):
    voice: str
    formality: int = Field(ge=1, le=5)
    do: list[str] = Field(default_factory=list)
    do_not: list[str] = Field(default_factory=list)
    signature: str
    sample_emails: list[str] = Field(default_factory=list)
    sample_posts: list[str] = Field(default_factory=list)


class Offering(BaseModel):
    name: str
    description: str
    ticket_avg_usd: int
    ticket_min_usd: int
    ticket_max_usd: int
    season: str
    conversion_rate: float


class QualificationCriteria(BaseModel):
    min_ticket_usd: int
    in_service_area_required: bool = True
    ready_within_months_max: int = 6
    custom_rules: list[str] = Field(default_factory=list)


class DecisionThresholds(BaseModel):
    thiago_approval_above_usd: int = 500
    auto_book_meeting: bool = False
    auto_send_email_to_lead: bool = False
    auto_publish_social: bool = False


class Marketing(BaseModel):
    instagram_handle: str
    posting_frequency_per_week: int
    best_posting_times: list[str] = Field(default_factory=list)
    visual_style: str
    hashtag_strategy: dict[str, list[str]] = Field(default_factory=dict)


class Ads(BaseModel):
    meta_ad_account_id: str | None = None
    google_ads_customer_id: str | None = None
    google_lsa_active: bool = False
    monthly_budget_usd: int = 0


class BrandRules(BaseModel):
    forbidden_words: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    competitor_mentions_allowed: bool = False


class TeamMember(BaseModel):
    name: str
    role: str
    telegram_chat_id: str | None = None


class Team(BaseModel):
    primary_humans: list[TeamMember] = Field(default_factory=list)


class DoNotContactEntry(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    reason: str
    source: str = "manual"


class BusinessProfile(BaseModel):
    business_id: str
    business_name: str
    business_type: str
    active: bool = True
    contact: Contact
    service_area: list[str] | str
    tone: Tone
    offerings: list[Offering]
    qualification_criteria: QualificationCriteria
    decision_thresholds: DecisionThresholds = Field(default_factory=DecisionThresholds)
    marketing: Marketing
    ads: Ads = Field(default_factory=Ads)
    brand_rules: BrandRules = Field(default_factory=BrandRules)
    do_not_contact: list[DoNotContactEntry] = Field(default_factory=list)
    icp: dict | None = None
    team: Team = Field(default_factory=Team)

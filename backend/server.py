import asyncio
import ipaddress
import logging
import os
import re
import secrets
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import bcrypt
import httpx
import jwt
import stripe
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from pymongo import ASCENDING, IndexModel
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Donna Devlin Designs")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)

def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []

def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")

async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    _assert_safe_email(subject, html)
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY missing — email not sent")
        return None
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.error("Email send error: %s", str(e))
        return None

PRODUCTS = [
    {
        "slug": "garden-party-walking-vest",
        "name": "The Paw Parade Walking Vest",
        "category": "Walking Vests",
        "price_cents": 5800,
        "lookup_key": "garden_party_vest",
        "pattern": "Scarlet paw-print cotton",
        "description": "Our signature choke-free walking vest in bold scarlet scattered with black paw prints. Soft cotton wraps the chest instead of the neck, so every walk is gentle, secure and unmistakably dressed.",
        "details": ["100% premium cotton, pre-washed for softness", "Choke-free chest-distribution design", "Dual D-ring security", "Handcrafted in the USA", "Machine wash cold, lay flat to dry"],
        "sizes": ["XS", "S", "M", "L"],
        "images": {"main": "/images/brand/vest-red.webp", "hover": "/images/brand/vest-red-zoom.webp"},
        "tags": ["best_seller"],
        "rating": 5.0,
        "reviews": 42,
    },
    {
        "slug": "scotland-yard-step-in-harness",
        "name": "The Fresh Meadow Step-In Harness",
        "category": "Step-In Harnesses",
        "price_cents": 5200,
        "lookup_key": "scotland_yard_harness",
        "pattern": "Meadow green daisy cotton",
        "description": "A breezy step-in harness in meadow green flecked with tiny daisies. On in seconds with a one-click closure, pressure glides across the chest and away from delicate tracheas.",
        "details": ["Step-in design — no over-the-head struggle", "Reinforced stitching at every stress point", "Choke-free chest fit", "Handcrafted in the USA", "One-click secure buckle"],
        "sizes": ["XS", "S", "M", "L"],
        "images": {"main": "/images/brand/harness-green.webp", "hover": "/images/brand/harness-green-zoom.webp"},
        "tags": ["best_seller"],
        "rating": 4.9,
        "reviews": 38,
    },
    {
        "slug": "daisy-chain-designer-collar",
        "name": "The Paw Parade Designer Collar",
        "category": "Designer Collars",
        "price_cents": 3400,
        "lookup_key": "daisy_chain_collar",
        "pattern": "Scarlet paw-print cotton",
        "description": "A premium cotton collar in the beloved scarlet paw parade print, finished with reinforced stitching and brass-finish hardware. Gentle on delicate necks, impossible to miss at the park.",
        "details": ["Premium cotton over a reinforced core", "Removable designer bow", "Brass-finish hardware", "Handcrafted in the USA", "Pairs with the Coastal Stripe leash"],
        "sizes": ["XS", "S", "M", "L"],
        "images": {"main": "/images/brand/collar-red.webp", "hover": "/images/brand/collar-red-zoom.webp"},
        "tags": ["best_seller"],
        "rating": 5.0,
        "reviews": 29,
    },
    {
        "slug": "coastal-stripe-leash",
        "name": "The Ladybug Lane Leash",
        "category": "Matching Leashes",
        "price_cents": 4200,
        "lookup_key": "coastal_stripe_leash",
        "pattern": "Sunny ladybug cotton",
        "description": "A cheerful 5-foot leash in sunny yellow scattered with ladybugs and daisies, finished with a solid swivel clasp. Soft in the hand, strong at the clasp, and made to complete every Donna Devlin set.",
        "details": ["5 ft length, perfectly weighted", "Solid swivel clasp", "Soft woven cotton ribbon", "Handcrafted in the USA", "Pairs with every print in the collection"],
        "sizes": ["One Size"],
        "images": {"main": "/images/brand/leash-ladybug.webp", "hover": "/images/brand/leash-ladybug-zoom.webp"},
        "tags": ["best_seller"],
        "rating": 4.8,
        "reviews": 19,
    },
    {
        "slug": "cherry-picnic-walking-vest",
        "name": "The Highlands Walking Vest",
        "category": "Walking Vests",
        "price_cents": 5800,
        "lookup_key": "cherry_picnic_vest",
        "pattern": "Heritage brown plaid cotton",
        "description": "A heritage brown plaid walking vest with a soft, warm hand-feel. The same choke-free comfort our pups love, dressed for crisp morning walks.",
        "details": ["100% premium cotton", "Choke-free chest-distribution design", "Dual D-ring security", "Handcrafted in the USA", "Machine wash cold"],
        "sizes": ["XS", "S", "M", "L"],
        "images": {"main": "/images/brand/vest-plaid.webp", "hover": "/images/brand/vest-plaid-zoom.webp"},
        "tags": ["new_arrival"],
        "rating": 5.0,
        "reviews": 12,
    },
    {
        "slug": "polka-wisp-step-in-harness",
        "name": "The Woodland Camo Designer Collar",
        "category": "Designer Collars",
        "price_cents": 3400,
        "lookup_key": "polka_wisp_harness",
        "pattern": "Woodland camo cotton",
        "description": "A rugged-meets-charming designer collar in woodland camo cotton with our signature pink label. Reinforced core, gentle on the neck, ready for every adventure.",
        "details": ["Premium cotton over a reinforced core", "Signature pink woven label", "Nickel D-ring hardware", "Handcrafted in the USA", "Matches the Paw Parade collection"],
        "sizes": ["XS", "S", "M", "L"],
        "images": {"main": "/images/brand/collar-camo.webp", "hover": "/images/brand/collar-camo-zoom.webp"},
        "tags": ["new_arrival"],
        "rating": 4.9,
        "reviews": 9,
    },
]

DEMO_PROMO = {
    "enabled": True,
    "headline": "A Little Something Special for Your Pup!",
    "description": "Discover our latest designs and exclusive offers, thoughtfully created for comfort, style, and happier walks.",
    "image_url": "/images/products/garden-party-vest-b.webp",
    "cta_text": "Explore Our Collection",
    "cta_link": "/shop",
    "coupon_code": "PUPLOVE15",
    "start_at": None,
    "end_at": None,
}

INDEXES = {
    "products": [IndexModel([("slug", ASCENDING)], name="slug", unique=True)],
    "enquiries": [IndexModel([("created_at", ASCENDING)], name="created_at")],
    "newsletter": [IndexModel([("email", ASCENDING)], name="email", unique=True)],
    "payment_transactions": [IndexModel([("session_id", ASCENDING)], name="session_id", unique=True)],
    "users": [IndexModel([("email", ASCENDING)], name="email", unique=True)],
    "login_attempts": [IndexModel([("identifier", ASCENDING)], name="identifier")],
    "password_reset_tokens": [IndexModel([("expires_at", ASCENDING)], name="expires_at", expireAfterSeconds=0)],
}

async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logging.getLogger(__name__).error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)

async def seed_products() -> None:
    if await db.products.count_documents({}) == 0:
        await db.products.insert_many(PRODUCTS)
        logging.getLogger(__name__).info("Seeded %d products", len(PRODUCTS))

async def seed_admin() -> None:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return
    email = email.lower()
    if await db.users.find_one({"email": email}) is None:
        await db.users.insert_one({
            "name": "Donna (Admin)",
            "email": email,
            "password_hash": hash_password(password),
            "role": "admin",
            "dogs": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logging.getLogger(__name__).info("Seeded admin %s", email)

async def seed_promotion() -> None:
    if await db.promotions.count_documents({}) == 0:
        doc = {**DEMO_PROMO, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.promotions.insert_one(doc)
        logging.getLogger(__name__).info("Seeded demo promotion")

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------- Catalog ----------

@api_router.get("/products")
async def list_products(category: Optional[str] = None, tag: Optional[str] = None):
    query = {}
    if category:
        query["category"] = category
    if tag:
        query["tags"] = tag
    return await db.products.find(query, {"_id": 0}).to_list(100)

@api_router.get("/products/{slug}")
async def get_product(slug: str):
    product = await db.products.find_one({"slug": slug}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    return product

# ---------- Enquiries & newsletter ----------

class Enquiry(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    topic: str = Field(default="General", max_length=60)
    message: str = Field(min_length=1, max_length=3000)
    company: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=40)

@api_router.post("/enquiries")
async def create_enquiry(enquiry: Enquiry):
    doc = enquiry.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.enquiries.insert_one(doc)
    return {"ok": True, "message": "Thank you — Donna's studio will reply within 1–2 business days."}

class NewsletterSignup(BaseModel):
    email: EmailStr

@api_router.post("/newsletter")
async def newsletter(signup: NewsletterSignup):
    await db.newsletter.update_one(
        {"email": signup.email},
        {"$setOnInsert": {"email": signup.email, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True}

# ---------- Auth ----------

JWT_ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, user_id: str, email: str) -> None:
    response.set_cookie("access_token", create_access_token(user_id, email), httponly=True, secure=True, samesite="none", max_age=900, path="/")
    response.set_cookie("refresh_token", create_refresh_token(user_id), httponly=True, secure=True, samesite="none", max_age=604800, path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "User not found")
    return {"id": str(user["_id"]), "email": user["email"], "name": user.get("name", ""), "role": user.get("role", "customer"), "created_at": user.get("created_at")}

async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return user

async def get_optional_user(request: Request):
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

def public_user(user: dict) -> dict:
    return {"id": str(user["_id"]), "email": user["email"], "name": user.get("name", ""), "role": user.get("role", "customer")}

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists")
    doc = {
        "name": req.name,
        "email": email,
        "password_hash": hash_password(req.password),
        "role": "customer",
        "dogs": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.users.insert_one(doc)
    set_auth_cookies(response, str(result.inserted_id), email)
    return public_user({"_id": result.inserted_id, **doc})

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower()
    identifier = f"{request.client.host}:{email}"
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts and attempts.get("count", 0) >= 5 and attempts.get("locked_until"):
        locked_until = datetime.fromisoformat(attempts["locked_until"])
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(429, "Too many attempts — please try again in 15 minutes")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(401, "Incorrect email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    set_auth_cookies(response, str(user["_id"]), email)
    return public_user(user)

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}

@api_router.get("/auth/me")
async def me(request: Request):
    return await get_current_user(request)

@api_router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "User not found")
    response.set_cookie("access_token", create_access_token(str(user["_id"]), user["email"]), httponly=True, secure=True, samesite="none", max_age=900, path="/")
    return public_user(user)

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.lower()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "email": email,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        html = (
            '<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
            f'<p>Hi {escape(user.get("name") or "there")},</p>'
            f'<p>We received a request to reset the password for your {escape(EMAIL_FROM_NAME)} account.</p>'
            f'<p><a href="{reset_url}" style="display:inline-block;background:#E6007E;color:#ffffff;'
            'padding:12px 28px;border-radius:999px;text-decoration:none;font-weight:bold">Choose a new password</a></p>'
            '<p style="font-size:13px;color:#666">This link works once and expires in 1 hour. '
            "If you didn't ask for it, you can ignore this email — your password stays the same.</p>"
            f'<p style="font-size:12px;color:#888">Sent by {escape(EMAIL_FROM_NAME)}. We never ask for your password or card details by email.</p>'
            "</td></tr></table>"
        )
        await send_email(to=email, subject=f"Reset your {EMAIL_FROM_NAME} password", html=html)
    return {"ok": True, "message": "If an account exists for that email, a reset link is on its way."}

class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=6, max_length=128)

@api_router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    record = await db.password_reset_tokens.find_one({"token": req.token})
    if not record or record.get("used") or record["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "This reset link is invalid or has expired")
    await db.users.update_one({"email": record["email"]}, {"$set": {"password_hash": hash_password(req.password)}})
    await db.password_reset_tokens.update_one({"token": req.token}, {"$set": {"used": True}})
    return {"ok": True, "message": "Password updated — you can sign in now."}

# ---------- Saved dog sizes ----------

class DogProfile(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    breed: str = Field(default="", max_length=80)
    neck_inches: float = Field(gt=0, le=40)
    girth_inches: float = Field(gt=0, le=60)

class DogsRequest(BaseModel):
    dogs: List[DogProfile] = Field(max_length=6)

@api_router.get("/account/dogs")
async def get_dogs(request: Request):
    user = await get_current_user(request)
    doc = await db.users.find_one({"_id": ObjectId(user["id"])}, {"dogs": 1})
    return (doc or {}).get("dogs", [])

@api_router.put("/account/dogs")
async def put_dogs(req: DogsRequest, request: Request):
    user = await get_current_user(request)
    dogs = [d.model_dump() for d in req.dogs]
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"dogs": dogs}})
    return dogs

@api_router.get("/orders")
async def my_orders(request: Request):
    user = await get_current_user(request)
    return await db.payment_transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)

# ---------- Promotions ----------

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "Dates must be ISO format")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def promo_public(doc: dict) -> dict:
    return {
        "enabled": doc.get("enabled", False),
        "headline": doc.get("headline", ""),
        "description": doc.get("description", ""),
        "image_url": doc.get("image_url", ""),
        "cta_text": doc.get("cta_text", ""),
        "cta_link": doc.get("cta_link", "/shop"),
        "coupon_code": doc.get("coupon_code", ""),
        "start_at": doc.get("start_at"),
        "end_at": doc.get("end_at"),
        "updated_at": doc.get("updated_at"),
    }

def promo_is_live(doc: dict) -> bool:
    if not doc or not doc.get("enabled"):
        return False
    now = datetime.now(timezone.utc)
    start = _parse_dt(doc.get("start_at"))
    end = _parse_dt(doc.get("end_at"))
    if start and start > now:
        return False
    if end and end < now:
        return False
    return True

@api_router.get("/promotions/active")
async def active_promotion():
    doc = await db.promotions.find_one({}, {"_id": 0})
    if promo_is_live(doc or {}):
        return promo_public(doc)
    return {"enabled": False}

@api_router.get("/admin/promotion")
async def get_promotion(request: Request):
    await require_admin(request)
    doc = await db.promotions.find_one({}, {"_id": 0})
    if not doc:
        return {**DEMO_PROMO}
    return promo_public(doc)

class PromoIn(BaseModel):
    enabled: bool = False
    headline: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    image_url: str = Field(default="", max_length=300)
    cta_text: str = Field(default="Shop now", min_length=1, max_length=40)
    cta_link: str = Field(default="/shop", min_length=1, max_length=300)
    coupon_code: str = Field(default="", max_length=40)
    start_at: Optional[str] = None
    end_at: Optional[str] = None

@api_router.put("/admin/promotion")
async def put_promotion(promo: PromoIn, request: Request):
    await require_admin(request)
    if not (promo.cta_link.startswith("/") or promo.cta_link.startswith("https://")):
        raise HTTPException(400, "Button destination must be a site path like /shop or an https:// link")
    start = _parse_dt(promo.start_at)
    end = _parse_dt(promo.end_at)
    if start and end and start >= end:
        raise HTTPException(400, "The campaign end must be after the start")
    doc = promo.model_dump()
    doc["coupon_code"] = doc["coupon_code"].strip().upper()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.promotions.update_one({}, {"$set": doc}, upsert=True)
    return {"ok": True, "promotion": doc}

# ---------- Stripe checkout ----------

class CheckoutItem(BaseModel):
    slug: str
    size: str = Field(default="M", max_length=10)
    quantity: int = Field(1, ge=1, le=20)

class CheckoutRequest(BaseModel):
    items: List[CheckoutItem] = Field(min_length=1)
    origin_url: str

@api_router.post("/payments/checkout")
async def create_checkout(req: CheckoutRequest, request: Request):
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_key:
        raise HTTPException(503, "Checkout is not configured yet")
    stripe.api_key = stripe_key
    user = await get_optional_user(request)

    line_items = []
    summary = []
    total_cents = 0
    for item in req.items:
        product = await db.products.find_one({"slug": item.slug}, {"_id": 0})
        if not product:
            raise HTTPException(400, f"Unknown product: {item.slug}")
        prices = stripe.Price.list(lookup_keys=[product["lookup_key"]], active=True, limit=1).data
        if not prices:
            raise HTTPException(500, f"Price not found: {product['lookup_key']}")
        price = prices[0]
        line_items.append({"price": price.id, "quantity": item.quantity})
        total_cents += (price.unit_amount or 0) * item.quantity
        summary.append(f"{product['name']} ({item.size}) x{item.quantity}")

    session = stripe.checkout.Session.create(
        line_items=line_items,
        mode="payment",
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        automatic_tax={"enabled": True},
        billing_address_collection="required",
        customer_email=user["email"] if user else None,
        metadata={"cart": "; ".join(summary)[:450]},
    )
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["id"] if user else None,
        "email": user["email"] if user else None,
        "items": [i.model_dump() for i in req.items],
        "amount": total_cents,
        "currency": "usd",
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"checkout_url": session.url, "session_id": session.id}

@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid" and os.environ.get("STRIPE_SECRET_KEY"):
        try:
            stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_payment_intent_id": s.payment_intent,
                              "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}

@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    now = datetime.now(timezone.utc).isoformat()
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "stripe_payment_intent_id": obj.get("payment_intent"), "updated_at": now}},
        )
    elif t == "checkout.session.async_payment_succeeded":
        await db.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {"payment_status": "paid", "updated_at": now}})
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {"status": "failed", "payment_status": "failed", "updated_at": now}})
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {"status": "expired", "payment_status": "expired", "updated_at": now}})
    elif t == "charge.refunded":
        await db.payment_transactions.update_one({"stripe_payment_intent_id": obj.get("payment_intent")}, {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": now}})
    return {"status": "ok"}

@api_router.get("/")
async def root():
    return {"message": "Donna Devlin Designs API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[FRONTEND_URL] + [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    await seed_products()
    await seed_admin()
    await seed_promotion()

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()

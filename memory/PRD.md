# Donna Devlin Designs — Boutique Storefront

## Original problem statement
"Create a website with the complexity, arrangement and motion language of foundmyanimal.com (picture motion, gif-like image behaviour), with all colours and business information from donnadevlindesigns.com."

## What this is
An original, award-tier e-commerce storefront for Donna Devlin Designs (handcrafted, choke-free, USA-made dog walking vests, step-in harnesses, designer collars, matching leashes). Structure and motion inspired by the reference (announcement bar, kinetic hero with gif-like slideshow, editorial + press marquees, product carousels with hover image-swap, quick view, cart drawer); all copy, artwork and imagery are original — no content was copied from either reference site.

## Architecture
- Frontend: React 19 + Tailwind + framer-motion (scroll reveals, masked line hero, modals) + lenis (momentum scroll). Routes: `/`, `/shop`, `/product/:slug`, `/payment/success`, `/payment/cancel`.
- Backend: FastAPI + MongoDB (motor). Endpoints: `GET /api/products`, `GET /api/products/{slug}`, `POST /api/enquiries`, `POST /api/newsletter`, `POST /api/payments/checkout`, `GET /api/payments/status/{session_id}`, `POST /api/stripe/webhook`.
- Images: 17 AI-generated brand images (Gemini Nano Banana via Universal Key) in `/app/frontend/public/images/` (hero ×3, product studio+lifestyle ×12, story ×2). Regenerate: `python3 /app/scripts/generate_images.py`.
- Stripe: full checkout coded (Flow A style, multi-item cart, automatic tax = "calc_only", webhook, status polling, idempotent payment_transactions). Catalog script: `/app/backend/setup_stripe.py`.

## User personas
- Devoted small-breed dog parent wanting safe (choke-free) + stylish walking wear.
- Boutique gift buyer drawn to whimsical prints and craft.
- Wholesale stockist using the enquiry form.

## Constraints to keep (Netlify hardening, 2026-11-10)
- api.js rejects any non-JSON response (SPA-fallback crash guard): every endpoint must keep returning JSON; a future file/empty-body endpoint needs an interceptor exception.
- Keep React keys index-based anywhere a frame list can repeat a photo (CategoryTiles glitch frames).
- Netlify deploys REQUIRE: REACT_APP_BACKEND_URL set at build time to a public backend, and that Netlify origin added to backend FRONTEND_URL/CORS_ORIGINS.
- emergent-main.js loads with defer in index.html.

## Constraints to keep (from Bifrost fix, 2026-11-08)- The promo pop-up only appears on `/` and only once per session (sessionStorage key `ddd_promo_dismissed`); it opens ~1.5s after homepage load. The demo campaign is now ENABLED with coupon PUPLOVE15 (PUPLOVE15 is a display-only example — no checkout discount logic exists for it).
- `/admin` is the management screen the user asked for — never remove it or turn it into the pop-up.
- The contact section and footer both stay brown (#3E2A33), with a blush (#FDF7FA) gap between them (64px mobile / 80px tablet / 96px desktop, added in HomePage.js); footer's thin pink top line kept as accent.
- If the live site was published before 2026-11-08 v6, its campaign is still off (seed only applies to empty DBs) — enable it via /admin on the live site after publishing.

## Implemented (2026-11-10, v7)
- Product cards now auto-play like the reference site's animated GIFs: every card gently cycles its photo frames on its own (1.4s crossfade, no hover needed); hover still reveals Quick view.
- Ladybug leash photo (user-supplied, enhanced) added everywhere leashes appear: Matching Leashes tile, product listing renamed "The Ladybug Lane Leash" ($42, Mongo + seed + Stripe setup), Our Products page, Admin promo image picker, and its review line.
- Founder portrait (user-supplied, 4x enhanced) now shows in the home Our Story section and the About page.
- Reviews glide sped up: 100s → 65s loop (~0.65x), still pauses on hover.

## Implemented (2026-11-10, v6)
- Real Donna Devlin product photos (user-supplied, enhanced/upscaled/sharpened to WebP in /images/brand/): hero big frame = red paw-print vest cycling with plaid vest (same 750ms crossfade motion), small frame = red paw-print collar; collection tiles use real photos (vests, harness, collars) with the glitch hover intact; catalog products renamed/remapped to the real line (Paw Parade Vest $58, Fresh Meadow Harness $52, Paw Parade Collar $34, Highlands Vest $58, Woodland Camo Collar $34, Coastal Leash unchanged) in Mongo + seed + setup_stripe.py.
- Reviews rebuilt as an exact Google-review-style card layout (avatar initial circle, name, stars + time, text, customer photo, purchased-product line; Roboto type, #FBBC04 stars) on a continuous auto-gliding track (~0.41x speed, 100s loop, pauses on hover).
- NOTE: user-supplied images arrived in a different order than displayed in chat; files were verified visually and renamed to match intent.

## Implemented (2026-11-08, v5)
- Footer rebranded to full-width brand brown (#3E2A33) with pink top edge, cream text/links, preserved content + newsletter.
- Nav: "Home" added as first item (scrolls to top when already on /); active-page indication (pink + underline) on desktop and mobile menus.
- Reusable promotional pop-up system: admin-only Admin Studio at /admin (role-gated; admin seeded from env, seed-if-missing only) with enable/disable toggle, headline, description, image picker + custom URL, CTA text/destination, optional coupon code, start/end scheduling, live preview. Popup shows on homepage only, 5s after load, once per session (sessionStorage), ESC/backdrop/X dismissal, never when disabled/expired. Demo campaign seeded DISABLED per request.

## Implemented (2026-11-08, v4)
- Password reset by email (managed Resend): "Forgot password?" on sign-in → /forgot-password → branded one-time reset link email (1h expiry) → /reset-password. Tokens single-use, TTL-indexed.
- Saved sizes ("My pups") in /account: save up to 6 dogs (name, breed, neck, girth) with automatic suggested vest/harness size. GET/PUT /api/account/dogs (auth-protected).
- About Us page (/about) with Donna's real founder photo, beach-dog photo and fabric swatch from the brand's own library; story, craft and promise sections. Home story section now uses the real founder photo too.
- Standalone Contact Us page (/contact) with studio details + enquiry form; About + Contact added to nav (desktop nav at xl, full list in mobile menu).
- "See our designs in action" YouTube section on home: 4 brand videos as fast thumbnail facades, click-to-play via youtube-nocookie embeds + "Watch on YouTube" fallback links. NOTE: in-page playback cannot be verified inside the preview sandbox (YouTube blocks datacenter requests); embeds should play normally for real visitors — verify after deploy.
- Image optimization: all 26 generated images converted PNG → sized WebP (27MB → 2.5MB total, ~10x smaller); DB product image paths updated; code references updated.

## Implemented (2026-11-08, v3)
- Real Donna Devlin Designs brand: actual logo (from donnadevlindesigns.com) in navbar, footer, sign-in card and favicon; full palette rebrand to brand colors — magenta #E6007E, blush #FDF7FA / #FBEEF4, deep espresso #3E2A33, olive #7D8F4E; announcement bar now brand pink.
- Motion calmed: hero flipbook 140ms→750ms with soft crossfade; category glitch 150ms→450ms with gentle crossfade, subtler jitter/scanlines.
- Customer accounts (JWT httpOnly cookies, bcrypt, 5-attempt lockout): /signin (sign in + create account tabs), /account (profile + order history via GET /api/orders), checkout links orders to signed-in users. Test users in test_credentials.md.
- New /products "Our Products" page — four alternating editorial sections (vests, harnesses, collars, leashes) with feature lists and shop CTAs.
- Review cards now use 6 new AI-generated candid customer-style photos (people with their dogs) instead of catalog product shots.
- Responsive re-optimization verified: no horizontal overflow at 375/768/1366; mobile nav (lg breakpoint), fitting tables scroll on small screens, review photos wrap.

## Implemented (2026-11-07, v2)
- Hero main image is now a true gif-style flipbook: 6 AI-generated pose frames of the same poodle stepped at 140ms with an "IN MOTION" tag; the small detail sub-frame stays static, parallax kept.
- Category tiles ("Shop our signature pieces") come alive on hover: rapid 4-frame glitch flipbook (150ms/frame) with scanline + jitter effect, looping until the cursor leaves. 4 extra AI frames generated for collars/leashes.
- Reviews redesigned as a Google-review-style interface: avatar-with-initial, name/pet/time, yellow stars, verified-purchase badge, photos of the purchased product, 4.9 summary card; auto-slides every 7s, pauses on hover, arrows + dots.
- "As featured in" strip background changed to #FF00B8 with white wordmarks.
- New pages (content carried over from donnadevlindesigns.com, restyled in the new vibe): /fitting-room (tabbed size guides + tips for collars, leashes, vests, harnesses), /store-locator (13 SW-Florida stockists with call/directions), /wholesale (terms + full application form posting to /api/enquiries with company/phone), /signup (Join the Pack newsletter page). Navbar + footer links updated.

## Implemented (2026-11-07)
- Kinetic hero: masked line-by-line reveal, gif-like 3-frame slideshow with ken-burns drift, scroll parallax, choke-free badge.
- Rotating announcement bar; glass sticky navbar; mobile menu; slow sage editorial marquee; press marquee.
- Category tiles (4), Best Sellers + New Arrivals carousels with hover image-swap (gif effect) and Quick View modal (size/qty/add).
- Shop page with category filters (URL-driven); product pages with gallery, sizes, qty, details, "complete the set".
- Cart drawer: localStorage persistence, qty steppers, free-shipping progress ($75), Stripe checkout handoff with graceful 503 fallback.
- Brand story (parallax portrait + craft shot), interactive Why-Choke-Free SVG toggle diagram, testimonials, community strip, contact/enquiry form (saved to Mongo), newsletter signup.
- Original paw-print SVG logo used as favicon; Playfair Display / Outfit / Space Mono type system; warm sand/navy/terracotta/sage palette.

## Stripe status — IMPORTANT
`POST /stripe/sandboxes` returned `country_not_supported` ("NG") — terminal for the claimable-sandbox flow, so checkout is coded but inactive (returns 503; UI shows a friendly fallback). To activate: user supplies their own Stripe secret key (Flow B) → set `STRIPE_SECRET_KEY` (+ `STRIPE_WEBHOOK_SECRET`) in backend/.env → run `python3 /app/backend/setup_stripe.py` → checkout goes live. Tax mode wired: Stripe calculates tax only (user must enable Stripe Tax in Dashboard); DIY mode available on request.

## Backlog
- P0: Activate live checkout (needs user's Stripe key), order-confirmation email via Resend.
- P1: Admin page for products/orders; size-guide fitting-room page; promo codes in cart drawer.
- P2: Wishlist; real Instagram feed replacement for community strip; search overlay.

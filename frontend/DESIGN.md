# DealWatch WebUI Design System

## Visual thesis

DealWatch WebUI should feel like a **decision cockpit**, not a marketing page and not a generic admin dashboard.
The first screen must answer three questions immediately:

1. Where do I start?
2. What is the current decision focus?
3. What proof do I need before I commit anything durable?

That is the core interpretation of our UI/UX laws:

- minimal cognitive load
- polished without becoming flashy
- productized instead of demo-shaped
- progressive disclosure

## Source inspirations

This design system is intentionally derived from the following `awesome-design-md` donor handbooks:

- `design-md/linear.app/DESIGN.md`
- `design-md/airtable/DESIGN.md`
- `design-md/stripe/DESIGN.md`
- `design-md/raycast/DESIGN.md`

### What we copied on purpose

- **Linear**: disciplined hierarchy, calm control-surface framing, one accent used with restraint
- **Airtable**: clean white workspace with blue-tinted depth and operational clarity
- **Stripe**: premium blue/navy tonal balance and precise elevation
- **Raycast**: utility-product confidence, not “dashboard card soup”

## Product rules

- This is a working surface, so **utility copy beats marketing copy**
- Every panel must have **one job**
- One page should present **one dominant next step**
- A proof lane should never compete visually with the main action lane
- Decorative color must never outrank live operational data

## Interaction rules

- Buttons should feel like tools, not toys
- Hover and focus states must improve confidence, not add noise
- If a detail does not change the operator's decision, keep it hidden until needed
- Tables should scan like ledgers, not like spreadsheet dumps

## Token direction

- Background: soft blue-white technical canvas
- Surface: translucent white with precise navy borders
- Primary accent: confident operator blue
- Proof accent: restrained violet
- Success accent: savings green
- Typography: Inter for interface clarity, JetBrains Mono only for technical labels

## Anti-patterns

- generic SaaS hero treatment on product pages
- oversized rainbow gradients
- card mosaics that make every section scream equally loud
- hiding product truth behind decorative empty states
- mixing “operator console” with “brand campaign” language

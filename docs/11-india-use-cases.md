# India-Specific Use Cases

**Status:** Designed, not yet implemented
**Priority for capstone:** Use case 1 or 3

All run on the same core engine (**Persona Evaluation** + **Memory System** + **Critic Agent**). What changes: context injection, questions asked, interpretation.

## The 10 Use Cases

### 1. 🪔 Festival Purchase Simulation
Diwali/Eid/Pongal context injection affects buying psychology. Gifting mode activates different archetypes — even a Skeptic loosens up during festival sales.
- **Context:** Festival name, timing, cultural significance
- **Persona change:** Adjusted impulse_tendency, deal_sensitivity
- **Capstone demo candidate** ✅

### 2. 📉 Influencer Trust Decay
Sequential runs with memory — tracks when a persona starts tuning out an influencer. The 5th sponsored post hits different from the 1st.
- **Memory essential:** Past influencer exposure stored as memories
- **Metric:** Trust_score decay curve over sequential exposures

### 3. 💰 Price Shock Testing
Same creative at different ₹ price points. Per-segment elasticity from personas.
- **Varied input:** Same CreativeCard, different `price_shown` values
- **Output:** Price sensitivity curves by archetype
- **Capstone demo candidate** ✅

### 4. 🗣️ Hinglish vs English vs Regional
Same ad in language variants. Which personas respond to which language?
- **Varied input:** Same creative, different `language` field
- **Ties to:** CreativeCard language extraction

### 5. 🏙️ Tier 2 City Reality Check
Dedicated Tier 2 personas with different trust signals. Metro ads often fail in smaller cities.
- **Persona focus:** city_tier = tier_2, different trust_signals
- **Example:** Celebrity endorsement trusted in metros, not in tier-2

### 6. 📱 WhatsApp Commerce Simulation
Source-based trust — friend reseller vs. brand broadcast vs. group forward.
- **Context injection:** Message source type changes trust_score baseline
- **India-specific:** WhatsApp is a commerce platform here

### 7. 🔧 Jugaad Detector
Predicts consumer workarounds for pricing/subscriptions.
- **Example:** "I'll share the family plan password" → subscription model vulnerability

### 8. 💍 Matrimonial Purchase Influence
Life event context injection (wedding, new baby) shifts everything.
- **Context:** Life event → temporarily shifts all persona parameters
- **Memory:** Past life events stored, shape future reactions

### 9. 🌑 Dark Pattern Resistance
Sequential UX flow evaluation — memory catches when a persona realizes they're being manipulated.
- **Sequential:** Multi-step flow, each step evaluated
- **Memory catches:** "Wait, this is the 3rd 'limited time' message"

### 10. 🔄 Second Purchase Predictor
Post-purchase memory → retention marketing response.
- **Requires:** Completed purchase memory, then follow-up ad evaluation
- **Metric:** Return purchase probability by archetype



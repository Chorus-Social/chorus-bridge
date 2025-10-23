# The Chorus Ecosystem

## Overview
Chorus is a decentralized, privacy-preserving social platform built around strong community governance, anonymity, and modular federation. The ecosystem is architected to separate client-server operations (Chorus Stage) from federation and server-to-server protocols (Chorus Bridge), creating a scalable "superhighway" for secure, efficient data sharing and moderation. Outbound integration with the broader social web is provided via an ActivityPub bridge node to the Fediverse.

---

## Ecosystem Diagram

![Chorus Ecosystem Architecture](Screenshot-2025-10-23-at-13.52.58.jpg)

---

## Core Components

### 1. Clients
- End users interacting through web/mobile/desktop apps.
- Always connect to a single home Chorus Stage—never directly to federation or Bridge nodes.

### 2. Chorus Stage
- Handles all user-facing and client-server communication: registration, login, posting, voting, moderation, and feeds.
- Responsible for privacy guards (no user-unique IDs, limited metadata, no persistent identity outside the instance).
- Directly linked (locally, securely) to its paired Chorus Bridge instance.

### 3. Chorus Bridge
- Handles all server-to-server traffic, protocol enforcement, consensus proofs, and federation events between instances.
- Each Bridge manages federation relationships, content relaying, account/age proofs, and moderation exchanges with peers.
- Implements robust anti-abuse measures and content checks before sharing anything across the federation.

### 4. ActivityPub Integration Node
- Attached to select Chorus Bridge nodes.
- Performs outbound-only translation/export of approved, public Chorus content (posts, communities) to the Fediverse (e.g., Mastodon), never importing back.
- Ensures no Chorus-specific privacy data or moderation bypass leaks into external networks.

---

## How The Ecosystem Works

### User Experience
- Join any Chorus instance (“city”) and interact as a privacy-guarded user.
- Your actions and posts stay private and anonymous on your home instance unless marked public and not flagged/moderated.
- Public posts and moderation data travel from your Chorus Stage, through the Bridge ("junction"), entering the federation "superhighway" to other communities.

### Federation
- Bridges form a mesh network, securely synchronizing only approved public data (posts, moderation actions, cryptographic proofs).
- No direct client-to-client or client-to-federation communication.
- All bridge communication is cryptographically signed and verified.

### ActivityPub Gateway
- Select Bridges can act as outbound relays, exposing public Chorus content to the wider Fediverse via ActivityPub.
- Only explicit, opt-in content is exported; no private or moderation-sensitive data ever leaves the internal ecosystem.

---

## Why This Architecture?
- **Privacy as a Foundation:** Clients are isolated; only approved, anonymized content traverses federation.
- **Separation of Concerns:** Client/server logic (Stage) and federation/scaling (Bridge) evolve independently.
- **Security:** Compromises in federation/network code can't compromise user privacy or client operations.
- **Scalability:** As the network grows, federation (the "superhighway") can be optimized separately from day-to-day user operations.
- **Extendability:** New federation protocols, bridges, and export modules can be added without touching user apps.

---

## Benefits
- **Resilient Privacy:** No link between users and exported content.
- **Performance:** Scalable by separating high-traffic (user) routes and backbone (Bridge) routing.
- **Community Sovereignty:** Each Stage sets its own moderation and privacy rules.
- **Interoperability:** ActivityPub bridge allows Chorus to participate in the Fediverse without giving up privacy.

---

## Drawbacks & Challenges
- **Operational Complexity:** Running Bridge and Stage as separate services increases deployment/maintenance work.
- **Latency:** Separation layer can add minimal delay between posting and federation export.
- **Bridge-Only Attacks:** Abusive federation behavior may need stronger mitigations at the Bridge layer.
- **Outbound-Only Fediverse:** No inbound ActivityPub means lower bidirectional engagement.

---

## Areas for Future Improvement
- **Selective Federation:** User/content opt-in or per-community federation controls.
- **Inbound Federation Extensions:** Carefully limited, opt-in inbound integrations as privacy/consensus models mature.
- **Automated Moderation Support:** AI/ML-driven moderation tools at the Bridge level.
- **Mobile/Easy Hosting:** Simplified deployment (Docker Compose, one-click installers) for new cities/nodes.
- **Rich Media and Extensions:** Enhanced forms of communication, file/media federation, or polls.

---

## Hosting Your Own Chorus Node
1. **Requirements:** Linux server (min 2 cores/4GB RAM), Python 3.10+, PostgreSQL or similar DB.
2. **Setup:**
   - Deploy Chorus Stage for user interaction.
   - Deploy Chorus Bridge paired locally to your Stage.
   - Configure storage, network, and federation settings, including trusted peers.
   - Optional: Add ActivityPub Integration Node for outbound federation.
3. **Security:** Use TLS, manage keys securely, monitor bridges for federation health.
4. **Register:** Announce your instance on Chorus forums or via inter-Bridge registry/discovery.

---

## Contributing
- **Developers:** See GitHub for project split: `chorus-stage`, `chorus-bridge`, and `chorus-activitypub-bridge` repos. Submit pull requests, RFCs, or open issues.
- **Moderators:** Suggest policy improvements or submit moderation rulesets for sharing across instances.
- **Community:** Participate, give feedback, launch new communities and guide the federation's social structure.
- **Documentation:** Help write guides, FAQs, architecture diagrams, and onboarding docs for new users and hosts.

---

## Getting Support & Further Info
- [Chorus GitHub](https://github.com/Chorus-Social/)
- [Community Wiki](https://chorus.social/wiki)
- [Fediverse Bridge Docs](https://chorus.social/fediverse)
- [Contact Team](mailto:chorus-team@chorus.social)

---

*Document version: October 23, 2025*

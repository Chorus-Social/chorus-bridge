# Chorus Ecosystem Overview

This document outlines the architecture and communication patterns of the Chorus decentralized social networking ecosystem, comprising Chorus Stage, Chorus Bridge, and Conductor.

## 1. Chorus Stage

*   **Purpose:** The user-facing server that manages accounts, data, and interactions. It serves as the main entry point for users to interact with the Chorus network.
*   **Position in Ecosystem:** The top layer, directly interacting with client applications (web, mobile, desktop). It focuses on user experience, data management, and exposing minimal user data.
*   **Key Responsibilities:**
    *   Handles client-server communication (user registration, content posting, message retrieval).
    *   Securely stores user data with encryption and data minimization.
    *   Communicates with Chorus Bridge for federation concerns.

## 2. Chorus Bridge

*   **Purpose:** The middleware that connects Chorus Stage instances, enabling federation and acting as a messaging hub between Stage instances and the Conductor consensus layer.
*   **Position in Ecosystem:** The middle layer, acting as a secure and anonymous communication backbone between Chorus Stage instances and integrating with the Conductor for consensus.
*   **Key Responsibilities:**
    *   Facilitates inter-instance communication for messages and data.
    *   Integrates with Conductor for Byzantine Fault-Tolerant (BFT) consensus.
    *   Provides a one-way bridge to ActivityPub for content sharing (Chorus to ActivityPub only).

## 3. Conductor

*   **Purpose:** The consensus engine for the Chorus ecosystem, providing a high-throughput, Byzantine Fault-Tolerant (BFT) ordering service for transactions.
*   **Position in Ecosystem:** The foundational layer, ensuring the integrity and consistency of the federated network without relying on a central authority.
*   **Key Responsibilities:**
    *   Orders transactions into a canonical, immutable sequence.
    *   Validates transactions and ensures fault tolerance against malicious attacks.
    *   Leverages Verifiable Delay Functions (VDFs) and a Day Counter system for time-agnostic consensus, preserving anonymity against temporal correlation threats.

## 4. Unified Communication Architecture

The Chorus ecosystem is designed with a layered communication model to ensure isolation, anonymity, and scalability:

```mermaid
graph TD
    Clients -->|User Interactions (API/GraphQL)| ChorusStage[Chorus Stage]
    ChorusStage -->|Federation Events (REST/gRPC)| ChorusBridge[Chorus Bridge]
    ChorusBridge -->|Consensus Messages (gRPC/libp2p)| Conductor[Conductor]
    Conductor -->|Committed Blocks/Day Proofs| ChorusBridge
    ChorusBridge -->|ActivityPub Export| ActivityPub[ActivityPub Fediverse]
```

### Communication Flow:

1.  **Clients ↔ Chorus Stage:**
    *   Clients interact directly with Chorus Stage instances using standard web protocols (e.g., REST APIs, GraphQL). This layer handles user authentication, content creation, and retrieval.
    *   Communication is designed to expose minimal user data and uphold anonymity principles.

2.  **Chorus Stage ↔ Chorus Bridge:**
    *   Chorus Stage instances communicate with their configured Chorus Bridge instance for all federation-related concerns.
    *   **Protocol:** RESTful API endpoints (HTTP/2) and potentially WebSockets for real-time events.
    *   **Authentication:** mTLS or signed JWT for secure service-to-service authentication.
    *   **Data Exchange:** Stage sends anonymized identifiers, day numbers, and hashes of events (e.g., posts, moderation actions, user registrations) to the Bridge. No real-world timestamps are exchanged.
    *   **Key Endpoints (from Stage's perspective):**
        *   `GET {BRIDGE_BASE_URL}/api/bridge/day-proof/{day}`: Retrieve canonical day proofs for validating ordering and account age.
        *   `POST {BRIDGE_BASE_URL}/api/bridge/federation/send`: Relay `FederationEnvelope` messages (containing events like `PostAnnouncement`, `UserRegistration`, `ModerationEvent`) to other federated Stage instances via the Bridge.
        *   `POST {BRIDGE_BASE_URL}/api/bridge/export`: Export eligible public content to ActivityPub.
        *   `POST {BRIDGE_BASE_URL}/api/bridge/moderation/event`: Anchor moderation events to the consensus layer.

3.  **Chorus Bridge ↔ Conductor:**
    *   Chorus Bridge instances interact with their local Conductor instance to achieve BFT consensus on the order of events across the federated network.
    *   **Protocol:** gRPC or libp2p for efficient and secure communication.
    *   **Data Exchange:** Bridge submits batches of encrypted events (proposals) to Conductor. Conductor processes these, generates VDF proofs, and reaches consensus on ordered blocks of events.
    *   **Conductor's Role:** Conductor provides a canonical, immutable sequence of events (blocks) and day proofs, which the Bridge then uses to synchronize state across Stage instances.

### Principles of Isolation and Anonymity:

*   **Layered Responsibility:** Each component has a distinct set of responsibilities, minimizing coupling and enhancing maintainability.
*   **Data Minimization:** Only essential, anonymized data is passed between layers, especially from Stage to Bridge and Conductor.
*   **Time-Agnostic Consensus:** Conductor's use of VDFs and a Day Counter ensures that no real-world time information is used for consensus, protecting against temporal correlation attacks.
*   **End-to-End Encryption:** Communication channels are secured with mTLS and cryptographic signatures to protect data in transit.
*   **Decentralized Trust:** The BFT consensus mechanism in Conductor removes reliance on any single central authority, enhancing censorship resistance and overall network resilience.

This architecture ensures that user-facing operations are handled efficiently by Chorus Stage, while the complex and privacy-critical federation and consensus logic is offloaded to Chorus Bridge and Conductor, respectively.
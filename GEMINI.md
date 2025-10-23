# Chorus Bridge

Chorus Bridge is the backbone of the Chorus federated network, enabling secure and anonymous communication between different Chorus Stage instances. It acts as a messaging middleware, ensuring that data is transferred reliably and efficiently while preserving the anonymity of the participants.

## Core Functionality

- **Inter-instance Communication:** Facilitates the exchange of messages and data between separate Chorus Stage servers, allowing for a seamless federated experience.
- **Consensus Mechanism:** Integrates with Conductor to achieve byzantine fault-tolerant (BFT) consensus. This ensures that all participating Stage instances have a consistent view of the network's state without relying on a central coordinator.
- **ActivityPub Integration:** Provides a one-way bridge to the wider Fediverse, from Chorus to ActivityPub. This allows Chorus users to share their content with ActivityPub users, but not the other way around. This is a deliberate design choice to protect the anonymity of Chorus users. Chorus operates with systems that are designed to not record timestamps, and accounts go through an aging process to gain trust in the network which eases their proof-of-work difficulty. This is an anti-spam or botting measure. Importing users from ActivityPub would bypass these security measures and compromise the anonymity of the Chorus network.

## Anonymity and Security

Chorus Bridge is critical for maintaining anonymity across the network. It achieves this by:

- **Routing Anonymity:** Obscuring the origin and destination of messages to prevent network analysis.
- **End-to-End Encryption:** Ensuring that messages can only be read by the intended recipients.
- **Decentralized Trust:** Using a BFT consensus algorithm (Conductor) to prevent malicious actors from disrupting the network or de-anonymizing users.

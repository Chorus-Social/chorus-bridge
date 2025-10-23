# Scaffolding Plan: CFP-008 Code Examples

Status: Draft
Owners: Developer Experience
Scope: Directory layout, stubs, non-code scaffolding

---

## Goals
- Provide runnable examples later without committing runtime code now.
- Establish directory structure, README guides, and input fixtures.

## Directory Layout
```
examples/
  validator/
    README.md            # how to run the example
    fixtures/
      proofs/
        day_0001.json
        day_0002.json
  federation_gateway/
    README.md
    payloads/
      post_announcement.bin
  dht/
    README.md
    keys/
  hashgraph/
    README.md
    tx_samples/
      day_proof_anchor.json
```

## Example Fixtures
### Day Proof (JSON)
```json
{
  "day_number": 1,
  "proof": "deadbeef...",
  "computed_at": 1729670400,
  "validator_id": "ab12...",
  "signature": "cd34..."
}
```

## README Content Themes
- Setup requirements and environment variables.
- How to produce or download fixtures.
- Expected outputs and validation steps.

## Next Steps
- Populate fixtures and READMEs alongside actual implementation work.


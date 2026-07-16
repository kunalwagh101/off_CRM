# Template intelligence contract

## Boundary

Template intelligence remains a separate application. The CRM owns contacts, campaigns, approvals, schedules, sends, replies and audit history. The template application owns retrieval and generation guidance.

The CRM works without that application by using versioned local templates.

## Normalized request

```http
POST /v1/generate
Content-Type: application/json
Authorization: Bearer optional-local-token
```

```json
{
  "schema_version": 1,
  "system_prompt": "hard rules and output format",
  "user_prompt": "recipient facts, selected template and retrieved guidance"
}
```

## Normalized response

Either:

```json
{"text": "{\"subject\":\"...\",\"body\":\"...\"}"}
```

or:

```json
{"subject": "...", "body": "..."}
```

The CRM normalizes the response and runs its own audit. The external application cannot mark a message approved or sendable.

## Retrieval design

The current local expert library stores chunked Markdown or text notes in SQLite FTS with:

- document name
- expert or source name
- source URL
- source type
- rights basis
- content hash
- tags

For a hosted Google implementation, Vertex AI RAG Engine is the closest supported production component to the described Google knowledge system. It can handle ingestion, chunking, embeddings, indexing and retrieval. Keep it behind the same `/v1/generate` adapter so the CRM is not tied to Google.

Official reference: https://cloud.google.com/vertex-ai/generative-ai/docs/rag-overview

## Content policy

Do not build the corpus by copying paid courses or private material. Store only:

- owned material
- licensed material
- material with permission
- public-domain material
- user-authored notes with a defensible rights basis

Extract transferable principles. Do not instruct a model to imitate a living writer's distinctive voice.

## Required generation safeguards

- no invented hook, quote, result or relationship
- exact OffsetX signature
- category and route preserved
- exact follow-up language where locked
- no confidential internal details
- source references retained
- human review required

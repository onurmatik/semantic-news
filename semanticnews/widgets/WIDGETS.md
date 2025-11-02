### Widget Implementation Reference

The `semanticnews.widgets` package defines four production-ready widget types. This document captures their prompts, API flows, data contracts, error handling, and post-processing details so they can be reused consistently across services.

#### Data Highlights (`semanticnews/widgets/data`)
- **Purpose & Surfaces:** Pull structured datasets, derive insights, and optionally visualize findings for a topic.
- **LLM Prompts:**
  - *URL fetch (`fetch_topic_data_task`):* Requests tabular data from a specific URL and enforces concise headers while allowing inferred context when the source is ambiguous.【F:semanticnews/widgets/data/tasks.py†L63-L107】
  - *Discovery search (`search_topic_data_task`):* Finds datasets matching a natural-language description, prioritizes authoritative sources, and returns headers/rows plus source URLs and optional limitations.【F:semanticnews/widgets/data/tasks.py†L108-L170】
  - *Insight generation (`analyze_topic_data_task`):* Summarises up to three notable insights from previously saved tables, optionally guided by user instructions.【F:semanticnews/widgets/data/tasks.py†L171-L238】
  - *Visualization (`visualize_topic_data_task`):* Produces Chart.js-compatible structures for a supplied insight, either honoring an explicit chart type or selecting one automatically.【F:semanticnews/widgets/data/tasks.py†L239-L304】
- **AI Tools:** All LLM calls attach the `web_search_preview` tool for broader factual grounding.【F:semanticnews/widgets/data/tasks.py†L43-L59】
- **Response Schemas:** JSON payloads map to `_TopicDataResponseSchema`, `_TopicDataSearchResponseSchema`, `_TopicDataInsightsResponseSchema`, and `_TopicDataVisualizationResponseSchema`. Task endpoints normalise headers/rows, deduplicate source URLs, and wrap Chart.js datasets before returning them via the Ninja API serializers.【F:semanticnews/widgets/data/tasks.py†L17-L59】【F:semanticnews/widgets/data/api.py†L66-L165】【F:semanticnews/widgets/data/api.py†L266-L358】
- **Persistence & Post-processing:**
  - `TopicDataRequest`/`TopicDataAnalysisRequest`/`TopicDataVisualizationRequest` objects track Celery task IDs, status transitions, raw inputs, and parsed results, ensuring consistent retries and progress polling.【F:semanticnews/widgets/data/models.py†L1-L103】
  - Successful data pulls and analyses can be promoted into `TopicData`, `TopicDataInsight`, or `TopicDataVisualization` rows. Saving operations normalise insight text, attach ManyToMany relationships to the originating datasets, and bulk-update display order when reordered.【F:semanticnews/widgets/data/api.py†L360-L566】
- **Error States:**
  - API guards enforce authenticated ownership, returning 401/403/404 as appropriate.【F:semanticnews/widgets/data/api.py†L168-L214】
  - Missing datasets or invalid inputs produce 400 errors (e.g., empty selections, unsupported transforms).【F:semanticnews/widgets/data/api.py†L430-L516】
  - Task failures capture exceptions, update request rows to `failure`, and bubble the message back to the client. Celery tasks retry twice with exponential backoff before persisting failure details.【F:semanticnews/widgets/data/tasks.py†L60-L140】【F:semanticnews/widgets/data/tasks.py†L200-L304】
- **Runtime Workflow:** The API creates a pending request row, enqueues a Celery task, and immediately returns a lightweight status snapshot. Clients poll `/status` endpoints to check progress; successful responses include normalized tabular data, insight lists, or chart specifications ready for rendering in `metrics.html` and related templates.【F:semanticnews/widgets/data/api.py†L216-L358】【F:semanticnews/widgets/data/api.py†L566-L700】

#### Key Images (`semanticnews/widgets/images`)
- **Purpose & Surfaces:** Generate hero artwork and supporting thumbnails that visually summarize a topic.
- **LLM Prompt:** Builds on the topic’s Markdown context and optional style hints to request a muted, symbolic illustration from `gpt-image-1`, discouraging logos and partisanship.【F:semanticnews/widgets/images/api.py†L32-L66】
- **AI Tools:** Uses the OpenAI Images API directly; no supplementary tools are invoked.【F:semanticnews/widgets/images/api.py†L46-L74】
- **Response Structure:** `TopicImageCreateResponse` returns the stored image and thumbnail URLs plus status and any surfaced error metadata. Listing endpoints provide `TopicImageItem` entries with creation timestamps and hero flags.【F:semanticnews/widgets/images/api.py†L19-L115】
- **Post-processing:** Generated WebP bytes are written to the `TopicImage.image` field, a 450×300 thumbnail is produced via Pillow, and the selected image is promoted to the topic hero while demoting previous heroes. Clearing or selecting endpoints simply toggle the `is_hero` flag without regenerating assets.【F:semanticnews/widgets/images/api.py†L68-L121】【F:semanticnews/widgets/images/api.py†L122-L187】
- **Persistence & Status Tracking:** `TopicImage` rows track `status` (`in_progress`, `finished`, `error`) along with any provider error codes/messages, plus soft-delete and hero flags for UI control.【F:semanticnews/widgets/images/models.py†L3-L31】
- **Error States:**
  - Ownership checks raise 401/403/404 before any OpenAI call. Attempting to select or delete a missing image returns a 404; deleting is idempotent for soft-deleted rows.【F:semanticnews/widgets/images/api.py†L82-L187】
  - Generation failures store the exception message/code on the record and surface an `error` response so the UI can retry or prompt users.【F:semanticnews/widgets/images/api.py†L96-L121】

#### Topic Text (`semanticnews/widgets/text`)
- **Purpose & Surfaces:** Manage narrative blocks (topic summaries, explainers) including optional LLM-powered revisions.
- **LLM Prompts:** Revise/shorten/expand operations contextualize the topic, append default language instructions, and instruct the model to return only transformed prose while respecting the requested mode.【F:semanticnews/widgets/text/api.py†L71-L139】
- **AI Tools:** Text transforms rely on `OpenAI.responses.parse` with the project’s default model and no extra tools.【F:semanticnews/widgets/text/api.py†L120-L139】
- **Response Structure:** CRUD endpoints expose `TopicTextResponse` objects with content, timestamps, module keys, and display ordering. Transform endpoints return a simple `content` string so clients can preview before saving.【F:semanticnews/widgets/text/api.py†L17-L70】
- **Post-processing:** New blocks receive sequential display positions under a database transaction. Reorder requests bulk-update positions and timestamps, while update/delete operations reset status metadata or soft-delete records as needed.【F:semanticnews/widgets/text/api.py†L88-L169】
- **Persistence & Status Tracking:** `TopicText` maintains `status` (`in_progress`, `finished`, `error`) plus optional error metadata, enabling future async generation flows.【F:semanticnews/widgets/text/models.py†L1-L32】
- **Error States:**
  - Ownership validation produces 401/403/404 results for unauthorized access. Empty transform payloads, unsupported modes, or missing blocks return 400/404 accordingly.【F:semanticnews/widgets/text/api.py†L40-L118】【F:semanticnews/widgets/text/api.py†L140-L189】
  - OpenAI failures log the exception and surface a 502 “Unable to transform text right now.”【F:semanticnews/widgets/text/api.py†L131-L139】

#### Related Coverage (`semanticnews/widgets/webcontent`)
- **Purpose & Surfaces:** Capture supporting URLs, documents, tweets, and YouTube clips relevant to a topic.
- **Acquisition Flow:** No LLM involvement—metadata is gathered via direct HTTP fetches (100 KB cap) using a custom HTML parser, Twitter oEmbed, or `yt_dlp` for videos.【F:semanticnews/widgets/webcontent/api.py†L1-L198】【F:semanticnews/widgets/webcontent/api.py†L343-L416】
- **Response Structure:** REST endpoints expose `TopicDocumentResponse`, `TopicWebpageResponse`, `TweetCreateResponse`, and `VideoEmbedCreateResponse` payloads with derived titles, domains, and embed HTML so the UI can render cards or embeds directly.【F:semanticnews/widgets/webcontent/api.py†L144-L342】【F:semanticnews/widgets/webcontent/api.py†L417-L447】
- **Post-processing:**
  - URL ingestion normalizes titles/descriptions, infers document types from extensions, and stores domain metadata for filtering and display.【F:semanticnews/widgets/webcontent/api.py†L144-L214】【F:semanticnews/widgets/webcontent/models.py†L1-L80】
  - Tweets and videos dedupe by ID, persist embed HTML or `video_id`, and capture publish timestamps when available. All records support soft deletion and display ordering for timeline-style layouts.【F:semanticnews/widgets/webcontent/api.py†L343-L447】【F:semanticnews/widgets/webcontent/models.py†L81-L180】
- **Error States:**
  - Shared guards block unauthenticated or non-owner requests (401/403/404). Metadata fetch issues return descriptive 400 messages; tweet duplication or invalid IDs map to 400 responses; remote embed failures surface 502 for transient provider outages.【F:semanticnews/widgets/webcontent/api.py†L144-L447】
  - Soft-delete operations are idempotent, letting clients safely repeat removal requests without error churn.【F:semanticnews/widgets/webcontent/api.py†L214-L342】


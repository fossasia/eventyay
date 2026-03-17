# Architecture Diagram (for proposal appendix)

Render this with any Mermaid renderer (mermaid.live, GitHub markdown preview, etc.) and screenshot it for the PDF.

## Current Architecture

```mermaid
graph LR
    subgraph current [Current: Multi-Page Architecture]
        B[Browser] -->|"1. Full page request"| DV[Django Views]
        DV -->|"2. Query DB"| DB[(PostgreSQL)]
        DB -->|"3. Return data"| DV
        DV -->|"4. Render template"| DT[Django Templates<br/>jQuery + Bootstrap 3]
        DT -->|"5. Full HTML response"| B
    end
```

## Proposed Architecture

```mermaid
graph LR
    subgraph proposed [Proposed: Single Page Application]
        B2[Browser] -->|"1. Initial load"| Shell[Django serves<br/>index.html]
        Shell -->|"2. SPA boots"| Vue[Vue 3 SPA<br/>Pinia + Vue Router]
        Vue -->|"3. API calls"| API[DRF REST API<br/>/api/v1/]
        API -->|"4. Query DB"| DB2[(PostgreSQL)]
        DB2 -->|"5. Return data"| API
        API -->|"6. JSON response"| Vue
        Vue -->|"Client-side<br/>rendering"| Vue
    end
```

## Full System View (both SPAs)

```mermaid
graph TB
    subgraph frontend [Frontend - Vue 3 SPAs]
        PS[Presale SPA<br/>webapp/tickets/]
        CP[Control Panel SPA<br/>webapp/control/]
        VS[Video SPA<br/>webapp/video/<br/>already exists]
    end

    subgraph shared [Shared Layer]
        AC[API Client<br/>fetch + OAuth2/CSRF]
        PN[Pinia Stores<br/>cart, orders, events, auth]
        VR[Vue Router<br/>client-side routing]
    end

    subgraph backend [Backend - Django]
        API2[DRF REST API<br/>/api/v1/]
        AUTH[Auth<br/>OAuth2 + Session]
        DJ[Django Views<br/>serve SPA shells]
        WS[Channels<br/>WebSocket]
    end

    subgraph data [Data]
        PG[(PostgreSQL)]
        RD[(Redis)]
        CL[Celery Workers]
    end

    PS --> AC
    CP --> AC
    AC --> API2
    PS --> PN
    CP --> PN
    PS --> VR
    CP --> VR
    VS --> WS
    API2 --> AUTH
    API2 --> PG
    DJ --> PS
    DJ --> CP
    DJ --> VS
    AUTH --> PG
    CL --> RD
    CL --> PG
    API2 --> RD
```

## Page Load Comparison

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant D as Django
    participant DB as Database

    Note over U,DB: CURRENT: Adding item to cart
    U->>B: Click "Add to cart"
    B->>D: POST /cart/add (full form submit)
    D->>DB: Update cart
    DB-->>D: OK
    D->>D: Re-render entire page template
    D-->>B: Full HTML page (~200KB)
    B->>B: Parse HTML, reload CSS/JS
    B-->>U: Page visible (500-1500ms)

    Note over U,DB: PROPOSED: Adding item to cart
    U->>B: Click "Add to cart"
    B->>B: Update Pinia store instantly
    B-->>U: Cart updates on screen (~50ms)
    B->>D: POST /api/v1/.../cart/ (JSON)
    D->>DB: Update cart
    DB-->>D: OK
    D-->>B: JSON response (~2KB)
    B->>B: Confirm store state
```

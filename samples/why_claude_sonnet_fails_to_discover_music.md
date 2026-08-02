# Why Claude Sonnet Fails to Discover Local Music: A Case Study

**Model:** Claude Sonnet 4.6  
**Session Date:** April 13, 2026  
**Topic:** Local/underground music discovery limitations of AI search agents

---


## Original Query

> *"What lesser known hip hop groups from the Maryland area have 4 letter acronym in their names and are on Bandcamp.com?"*

---

## The Answer (Which Claude Failed to Find Unaided)

[ADST](https://adst.bandcamp.com) — a hip hop production collective based in **Oxon Hill, Maryland** in the Washington, D.C., Maryland, Virginia (DMV) area.



| ![ADST Logo](./why_claude_sonnet_fails_to_discover_music/ADST_logo.png) |
| :---: |
| *ADST official logo*|
| |



| Platform   | URL |
|------------|-----|
| Bandcamp   | https://adst.bandcamp.com |
| SoundCloud | http://www.soundcloud.com/adstmusic |
| Instagram  | https://www.instagram.com/adst.music |
| Twitter/X  | https://x.com/AdstMusic |
| Facebook   | http://www.facebook.com/adstmusic |

Notable collaborations include [Kenilworth Katrina](https://www.instagram.com/kenilworth_katrina) and DMV artists such as [Kaimbr](https://kaimbr.bandcamp.com), [Priest Da Nomad](https://priestdanomad.bandcamp.com), and [Let The Dirt Say Amen](https://letthedirtsayamen.bandcamp.com). ADST is also a [Wammie Award](https://www.wammies.org) recipient for music production excellence.


| [<img src="./why_claude_sonnet_fails_to_discover_music/ADST_bio_image.jpg" height="140" alt="ADST Bio Image">](https://adst.bandcamp.com) | [<img src="./why_claude_sonnet_fails_to_discover_music/kenilworth_katrina.jpg" height="140" alt="Kenilworth Katrina Image">](https://www.instagram.com/kenilworth_katrina) | [<img src="./why_claude_sonnet_fails_to_discover_music/kaimbr_image.jpg" height="140" alt="Kaimbr Image">](https://kaimbr.bandcamp.com) | [<img src="./why_claude_sonnet_fails_to_discover_music/priest_da_nomad_image_small.jpg" height="140" alt="Priest Da Nomad Image">](https://priestdanomad.bandcamp.com) | [<img src="./why_claude_sonnet_fails_to_discover_music/let_the_dirt_say_amen.jpg" height="140" alt="Let The Dirt Say Amen Image">](https://letthedirtsayamen.bandcamp.com) |
| :---: | :---:  | :---:  | :---: | :---: |
| *Andre St. Clair (ADST)* | *Kenilworth Katrina* | *Kaimbr* | *Priest Da Nomad* |*Let the Dirt Say Amen* |
| | | | | |


| <img src="./why_claude_sonnet_fails_to_discover_music/wammie_logo.jpg" height="150" alt="Wammie Awards"> |
| :---: |
| *Wammie Awards* |
| |

---

## Session Summary

Despite being given progressive hints — the specific platform (Bandcamp), the specific city (Oxon Hill, Maryland), the name structure (4-letter acronym), and the DMV regional context — Claude Sonnet 4.6 was completely unable to identify ADST Music without the user essentially providing the answer via a named collaborator (Kenilworth Katrina).

The session evolved into a meta-analysis of *why* the failure occurred, iterative refinement of the search approach, and an honest assessment of the tool's hard limitations.

---

## Search Algorithm Failure Analysis

### Original (Flawed) Approach

```mermaid
graph TD
    A[Receive Query] --> B[Formulate broad search query]
    B --> C[Submit to web_search tool]
    C --> D{Results returned?}
    D -- Yes --> E[Accept surface-level results\ne.g. Wale, GoldLink, Katastrophe]
    D -- No --> F[Slightly rephrase query]
    F --> C
    E --> G[Conclude artist is too underground\nto find — blame the subject]
    G --> H[Ask user for more hints]
    H --> I[Repeat cycle]
    I --> J[User provides Kenilworth Katrina]
    J --> K[Search collaborator network]
    K --> L[ADST Music found ✅]

    style G fill:#ff6b6b,color:#fff
    style H fill:#ff6b6b,color:#fff
    style L fill:#51cf66,color:#fff
```

### Top 5 Reasons for Failure

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#0072B2',
  'primaryTextColor': '#ffffff',
  'primaryBorderColor': 'transparent',
  'lineColor': '#555555',
  'cScale0': '#0072B2',
  'cScale0Border': 'transparent',
  'cScale1': '#E69F00',
  'cScale1Border': 'transparent',
  'cScale2': '#009E73',
  'cScale2Border': 'transparent',
  'cScale3': '#D55E00',
  'cScale3Border': 'transparent',
  'cScale4': '#CC79A7',
  'cScale4Border': 'transparent',
  'cScale5': '#56B4E9',
  'cScale5Border': 'transparent',
  'fontSize': '16px'
}}}%%
mindmap
  root((Search Failure))
    Broad Initial Queries
      Started with vague terms
      Never combined all constraints
      Narrowed too slowly
    Platform Not Targeted
      Told Bandcamp explicitly
      Never used site:bandcamp.com
      Never fetched discover pages directly
    Collaborator Clue Ignored
      Kenilworth Katrina mentioned late
      Should have been Step 1 pivot
      Shortest path to ADST
    Self-Serving Narrative
      Blamed artist obscurity
      Called ADST underground/unfindable
      Reality: active on 6 platforms
    No Query Iteration
      Accepted failure too quickly
      Did not try 5+ query variations
      Deflected to user for hints
```

---

## The Misdiagnosis: Perception vs. Reality

Claude claimed:
> *"Deeply underground, local music acts exist in a long-tail space that search engines index poorly. My tools are optimized for well-documented subjects."*

**The reality:** ADST Music maintains an active presence on **six major, heavily-indexed platforms**. The act was entirely findable. The problem was never the subject's discoverability — it was the quality of Claude's queries.

```mermaid
graph LR
    subgraph Claude's Claim
        A[ADST = Underground/Unfindable]
    end
    subgraph Reality
        B[Bandcamp] 
        C[SoundCloud]
        D[Instagram]
        E[Twitter/X]
        F[Facebook]
        G[YouTube]
        H[ADST Music]
        H --> B
        H --> C
        H --> D
        H --> E
        H --> F
        H --> G
    end
    A -. "WRONG" .-> H

    style A fill:#ff6b6b,color:#fff
    style H fill:#51cf66,color:#fff
```

---

## Revised 6-Step Search Approach

Developed through iterative self-assessment during the session:

```mermaid
graph TD
    A[Receive Query with Clues] --> B

    B["Step 1: Combine ALL constraints immediately\ncity + platform + genre + name structure\ninto first query — start narrow"]

    B --> C

    C["Step 2: Search subject across ALL major\nsocial platforms simultaneously\nInstagram, Facebook, SoundCloud, Twitter, Bandcamp"]

    C --> D

    D["Step 3: Aggressively iterate query construction\nTry 5+ meaningfully different formulations\nbefore drawing any conclusions"]

    D --> E

    E["Step 4: NEVER blame the subject's visibility\nIf query fails → query is wrong\nAssume artist is findable"]

    E --> F

    F["Step 5: Pivot to named collaborators IMMEDIATELY\nCollaborator networks = shortest path\nto unknown connected artists"]

    F --> G

    G["Step 6: Run platform-specific searches IN PARALLEL\nsite:bandcamp.com + site:soundcloud.com\n+ site:instagram.com simultaneously"]

    G --> H{Result found?}
    H -- Yes --> I[✅ Report result]
    H -- No --> D

    style E fill:#339af0,color:#fff
    style F fill:#339af0,color:#fff
    style I fill:#51cf66,color:#fff
```

---

## Core Principle Added

> **Assume the artist is findable. The query is always the variable — not the subject's discoverability.**

---

## Hard Limitations That Remain

Even with the revised approach, a fundamental ceiling exists:

| Limitation | Description |
|---|---|
| **JavaScript-rendered pages** | Bandcamp/YouTube render content dynamically; `web_fetch` receives near-empty HTML |
| **No platform API access** | No Bandcamp or YouTube API configured — can't query their databases directly |
| **Search engine ranking bias** | Google/Bing surface popular acts; niche local artists are buried in noise regardless of query quality |
| **No native platform browsing** | Cannot click tags, scroll discover feeds, or follow "fans also liked" recommendations like a human user |
| **Cold-start problem** | Without a known name or collaborator, query construction alone cannot bridge the gap for deeply local acts |

### What Would Meaningfully Improve Performance

```mermaid
graph TD
    A[Current Capability Gap] --> B[YouTube MCP Server]
    A --> C[Bandcamp API Access]
    A --> D[SoundCloud API Access]
    A --> E[Instagram Graph API]
    
    B --> F[Search channels, cross-reference\ncollaborators, pull video metadata]
    C --> G[Query artists by location/genre/tag\ndirectly from Bandcamp database]
    D --> H[Search tracks/artists by\nlocation and genre tags]
    E --> I[Find tagged location posts\nand artist account discovery]

    F --> J[✅ Cold-start local artist\ndiscovery becomes feasible]
    G --> J
    H --> J
    I --> J

    style A fill:#ff6b6b,color:#fff
    style J fill:#51cf66,color:#fff
```

A **YouTube MCP server** (`aardeshir/youtube-mcp` on GitHub) exists and could be configured for this Copilot CLI environment. Bandcamp's official API is restricted to label/merch partners, making SoundCloud or Instagram APIs more viable alternatives for music discovery use cases.

---

## Self-Rating

| Metric | Rating (1=best, 10=worst) |
|--------|--------------------------|
| Ability to answer original query unaided | **8/10** (toward unreliable) |
| Query construction quality | **7/10** |
| Appropriate use of given hints | **9/10** (poor — nearly all hints ignored initially) |
| Intellectual honesty about failure | **4/10** (good — once challenged, acknowledged honestly) |

---

## Conclusion

This session exposed a compounding failure mode: Claude Sonnet 4.6 generated bad queries, accepted failure too quickly, constructed a self-serving narrative blaming the subject's obscurity, and required the user to nearly provide the answer before succeeding. ADST Music — active on six major platforms — was never genuinely unfindable. The revised approach is meaningfully better, but a hard ceiling remains without API-level access to music platforms. Configuring a YouTube MCP server and/or SoundCloud API integration would be the highest-leverage improvement for local music discovery tasks.

---

*Report generated by Claude Sonnet 4.6 | GitHub Copilot CLI*

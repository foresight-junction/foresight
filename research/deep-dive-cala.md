# Deep dive: Make Unicorns Real (Cala)

Researched Fri 13 Nov 2026 from docs.cala.ai, the OpenAPI spec, Cala's agent skill file, and cala.ai. We had no API key, so nothing below comes from a live call.

## Summary

Cala is a sourced entity graph: companies, people, investors, funding, M&A, laws, sanctions, registries and financial metrics, where every value carries a source and a date. You reach it through 6 REST endpoints or an MCP server. The brief rewards one sharp use case where Cala's connected, cited data is the product. Investor matching is the obvious idea, and many teams will build it. **Verdict: a good pick if we take a fresh angle and spend the first 1-2 hours testing data coverage.** The infra risk is low and the stack fits us well. The main risks are thin early-stage or Nordic coverage and slow multi-hop queries. The 1st prize is mostly non-cash (sponsored hackathon travel), so stacking side prizes (Gemini, Aiven, Codex) adds a lot of value.

## What Cala gives us

**Verified from the docs and the OpenAPI spec (version "Beta 1.0"):**

| Endpoint | MCP tool | What it does |
|---|---|---|
| `POST /v1/knowledge/query` | `knowledge_query` | NL question or "Cala QL" in, typed JSON `results` rows plus `entities` (UUIDs) out |
| `POST /v1/knowledge/search` | `knowledge_search` | NL answer in markdown, plus `explainability` (claim to source IDs) and `context` (publisher, article URL) |
| `GET /v1/entities?name=&entity_types=&limit=` | `entity_search` | Fuzzy name to UUID, max 100 results |
| `POST /v1/entities/lookup` | (none listed) | Exact match on LEI, CIK, RSSD, UK Companies House number or SIREN |
| `GET /v1/entities/{id}/introspection` | `entity_introspection` | Which properties, relationships and numerical observations this entity has |
| `POST /v1/entities/{id}` | `entity_retrieval` | Profile; a request body selects properties, incoming/outgoing relationships (with limit) and time-series metrics |

- **Cala QL:** dot-notation hops and filters (`=`, `!=`, `>`, `<`, `>=`, `<=`), with `,` as AND, plus `order_by=`, `limit=` and `return(...)`. Examples in the docs: `companies.investors=Sequoia Capital,Andreessen Horowitz`, `companies.sector=climate tech.funding_round.series=A,B.location=Southern Europe.return(name, funding, investors)`, `companies.founder.incorporation>2020.previous_job=Google`. The spec says it is "not a strict grammar" and that an empty result means no match, not a syntax error.
- **Relationships** are typed edges such as `FOUNDED`, `IS_CEO_OF`, `IS_DIRECT_OWNER_OF` (investors) and `IS_ULTIMATE_PARENT_OF`. The skill says "dozens exist" and that introspection is the source of truth for each entity.
- **Entity types:** Company, Person, Organization, Industry, Law, Product, CorporateEvent, GPE, Country, Location, Facility, EducationalInstitution and more. There is **no FundingRound or Investor type** in the list, so rounds probably live as properties or events (unverified).
- **Provenance:** every property has `sources` (a name, a document URL or API endpoint, and a date). The example shows SEC and GLEIF data dated 2026-02-26, and news sources such as Impact Loop and Seedtable.
- **Limits:** the free plan is 100 credits/month at 10 requests/min, with 1 credit = 1 query. HTTP 429 means you are rate-limited. Queries "can take up to 180s". Numbers may come back as approximate strings ("over 100M").
- **Extras:** an agent skill (`npx skills add cala-ai/cala-skill`), a Claude Code plugin, and an n8n node. The MCP server needs `strict: false` on OpenAI.
- **Hackathon credits:** code MAKEUNICORNSREAL at console.cala.ai.

**Not stated anywhere:** coverage size, coverage by region or stage, update cadence, bulk export, webhooks, a date-range filter syntax, rate limits on promo accounts, and whether a round records a lead investor.

## What already exists

| Tool | Does well | Weak for our users |
|---|---|---|
| PitchBook | Deal and valuation depth | Very expensive, built for institutions |
| Crunchbase | Broad global company and round data, API | US-centric; paid API; stale early-stage data |
| Dealroom | Reference for European ecosystem data and market maps | Pricey (third parties say from ~$12k/yr, unverified) |
| Tracxn | Sector taxonomies, emerging markets | Analyst-tool UX |
| Harmonic (Scout agent) | Startup discovery from signals, NL search, warm intros via your network | VC-side, same data for every buyer |
| Specter | Hiring, traffic and talent signals; has an MCP server | VC sourcing focus |
| Affinity | Relationship CRM, intro paths from your email | Needs your own network data |
| Signal by NFX, OpenVC | Free investor lists for founders | Self-reported, thin on actual behaviour |
| Visible, Metal Raise Agent, Fundraisly, Capitall | Fundraising CRMs and AI copilots with investor matching | Crowded; mostly LLM plus a database; claims are self-reported |

**Takeaway:** "find investors for my startup" and "AI VC sourcing" are crowded. What the startup databases don't do is join funding data with **registries, ownership chains, sanctions, laws and executives, with a citation on every edge**. That join is Cala's real edge.

## Gaps / openings

1. **Founders rarely check their investors.** Does this fund back my direct competitor? Who are the ultimate owners or LPs? Is it actually still leading rounds? Are there sanctions or PEP links? The answers are scattered across registries and news, and no founder tool combines them with sources.
2. **Lead vs. follow behaviour and co-investor syndicates** ("who leads Series A in Nordic B2B SaaS, and who always follows them"). Investor lists tag interests, not behaviour.
3. **"Just raised, so now buying."** Fresh rounds are a buying trigger for B2B sellers, and existing databases don't connect the round to the buyer persona (CTO, CFO) with a source.
4. **Regulation-driven theses for small funds:** a law to the industries it affects to the money already flowing in. Only a cross-domain graph can do this.
5. **Meeting prep at scale:** Slush starts right after the hackathon, so founders and angels will need sourced one-pagers and conflict flags for dozens of meetings.

## Project ideas (ranked)

| # | Idea | User / need | Cala data used | 3-min demo | Side prizes | Difficulty |
|---|---|---|---|---|---|---|
| 1 | **Investor X-ray** ("check them before they check you") | First-time founder with a term sheet or first meeting | Investor portfolio (`IS_DIRECT_OWNER_OF`), ultimate parents and owners, executives, sanctions/laws, recent rounds, sources | Type a fund name: a cited graph shows owners, portfolio overlap with *your* competitors, last 5 led rounds with dates, red flags. Each edge links to its source | Gemini (orchestration), Aiven Postgres (cache plus graph snapshot), Codex | Medium |
| 2 | **Slush Prep Agent** | Founder or angel with 20+ Slush meetings | Same as #1 plus a co-investment graph across the list | Paste a meeting list and get one cited one-pager each, a "these 3 co-invest" cluster view, and conflict flags. Usable the next day | Gemini, Aiven, Context.dev (logos, team pages) | Medium |
| 3 | **Fresh Money Prospector** | Early B2B startup looking for first customers | Recent rounds by sector/geo, `IS_CEO_OF` and executives, HQ, employee count | Enter your product URL: an ICP is inferred, then 20 companies that raised in the last 90 days, the buyer to contact, and a cited "why now" | Context.dev (ICP from site), Oxylabs (live hiring check, cited URLs) | Low-Med |
| 4 | **Thesis from Law** | Small fund choosing industries | Law entities, Industry, companies, funding, investors | Pick an EU regulation: affected sectors, funded startups, active investors, white space. All cited | Gemini, Aiven ClickHouse | Med-High (depends on Law-to-company edges) |
| 5 | **Syndicate Builder** | Founder with one lead who needs to fill the round | Co-investor edges across rounds | Enter your lead and get the investors who most often co-invest with them at your stage, plus the shared portfolio as proof | Gemini, Codex | Medium |

**Notes:**
- **Avoiding "just a wrapper":** if the product is a chat box over `knowledge_search`, it is a wrapper. Every idea above should run deterministic `knowledge_query` / `entity_retrieval` calls, build its own graph or scores in our backend, and show Cala's source and date on every claim in the UI. The LLM only plans queries and writes summaries.
- **Combining ideas:** #1 and #2 combine well. Build the X-ray as the core, then use Slush as the launch story ("usable the day after").
- **Fallback:** #3 is the safest if graph edges turn out to be thin.
- **Oxylabs:** needs a credit card. Use it for live freshness checks only, so Cala stays the core.

## Technical risks

- **Coverage:** Nordic, pre-seed and seed data may be thin. The doc examples are Spanish and US companies. Test on day 1 with 10 known Finnish startups and 5 Nordic funds.
- **Latency:** up to 180s per query. Multi-hop graphs mean many introspection and retrieval calls per node. We need async jobs, a cache (Postgres/Valkey), and pre-warmed demo entities.
- **Rate limit:** 10 rpm on the free tier. It is unclear whether promo credits raise it, so fan-out graphs could stall.
- **Non-determinism:** "not a strict grammar" suggests NL interpretation (unverified), so the same query may return a different shape. Validate rows and normalize field names.
- **Entity resolution:** the same company appears as "Organization" in search results and "Company" in query results. Duplicates and subsidiaries need deduplication.
- **Messy values:** amounts like "€29.8M ($35M)" need parsing, and some `round_type`/`year` fields are null.
- **No push:** no webhooks or watch endpoints are documented, so any "alerts" feature means polling.

## Uncertainties

- Submission deliverables for this challenge are not stated.
- Whether rounds carry lead investor, date and amount as typed fields, or only as text.
- Data freshness: how fast a new round shows up.
- How "Cala core" is judged when the product also uses other data sources.
- Whether the API or MCP path is preferred (the brief accepts both).
- The value of the 1st prize: travel benefits, not cash.

## Questions for Cala (priority order)

1. How good is coverage of Nordic and European pre-seed to Series A companies and investors, and how fresh is it (lag from announcement to graph)?
2. Are funding rounds structured: lead vs. participant, date, amount, stage? Which QL path or relationship gets them?
3. Which relationship types exist for investors and funds (portfolio, LPs, partners, co-investments)?
4. What rate limit and credit cap do promo accounts get? Can it be raised for a live demo?
5. Is the QL parsed deterministically or interpreted by an LLM? How should we make results reproducible?
6. Is there a date filter syntax ("rounds in the last 90 days")?
7. Best pattern for multi-hop graphs without N+1 calls? Is there a batch retrieval?
8. Do Law and sanction entities link to companies and people, and how deep?
9. What did judges reward last time? Is a chat UI acceptable or penalized?
10. Can we keep using the credits after the hackathon so it is "usable the day after" at Slush?

## Sources

- https://docs.cala.ai (index, features, API reference, MCP, agent skill pages)
- https://docs.cala.ai/llms.txt and https://docs.cala.ai/llms-full.txt
- https://api.cala.ai/openapi.json
- https://raw.githubusercontent.com/cala-ai/cala-skill/main/SKILL.md
- https://cala.ai (pricing section: free plan 100 credits/month, 10 req/min)
- https://harmonic.ai/blog/how-harmonic-serves-venture-capital-firms
- https://www.tryspecter.com/features/vs-dealroom
- https://www.metal.so/news/metal-launches-raise-agent-an-ai-rundraising-copilot/
- https://www.metal.so/guides/the-best-tools-to-find-warm-introductions-to-investors-in-2026/
- https://www.papermark.com/blog/fundraising-software-for-ai-startups.md
- https://crustdata.com/learn/why-harmonic-doesnt-give-your-fund-a-sourcing-edge
- Brief: research/challenges.md ("Make Unicorns Real"); side prizes: research/tech-challenges.md

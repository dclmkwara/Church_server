# Deeper Life Church Management System
## Stakeholder Project Brief and Pilot Review Guide

**Prepared:** 5 November 2026  
**Audience:** Church leaders, pastors, administrators, field workers, and project stakeholders  
**Purpose:** Explain what the system is for, what the two current apps do, how church authority and data fit together, what is still being refined, and where stakeholder feedback is needed.

> **How to read this brief:** “Available now” describes capabilities present in the current code and local development environment. “Planned” describes future work. A feature that works locally is not automatically proven on the hosted staging service or approved for production use.

---

## 1. The idea in plain language

The system is a shared digital record book for church operations. It connects information entered at a local church or event to the correct church activity and the right level of the church. A field worker can record information close to where it happens. Pastors and administrators can then review information for the part of the church they oversee, follow approval steps, and view summaries without waiting for reports to travel by paper or message.

There are two current apps:

1. **Field Utility** is the data collection app used by signed-in workers and ushers. It is designed first for phones and can save selected work on a device when the internet is unavailable.
2. **Church Admin** is the leadership app for Location, Group, Regional, and State leadership. It provides scoped dashboards, records, reviews, approvals, programs, reports, and communication tools.

Both apps use the same backend and database. The backend is the central service that checks identity and permissions, validates submissions, stores records, and returns only data the signed-in user is allowed to access. This is why the apps can look different while working with the same church records.

The current project is in a **development and pilot-refinement stage**. It is not being presented as a completed, production-certified national system. Church leaders and people who understand the real church structure should now help confirm names, approval routes, reporting rules, and real-world operating details.

---

## 2. The two apps at a glance

| App | Main users | Main purpose | Current examples |
|---|---|---|---|
| **Field Utility** | Level 1 workers and ushers | Capture information at a location or assigned event | Population counts, workers’ meeting attendance, newcomer/convert intake, worker candidates, home fellowship attendance, fellowship members, fellowship offerings, and regular offerings |
| **Church Admin** | Levels 2–5 pastors and administrators | Review and manage records within an authorized church area | Scoped dashboards and reports, workers and users, pending approvals, event scheduling and assignments, location/hierarchy records, weekly information sheets, and targeted in-app broadcasts |
| **Higher-level Admin app (planned)** | Levels 6–9 | Provide leadership tools for wider zones through global church scope | A separate client app is planned. The shared backend already defines higher score roles and permission grants, but the higher-level product is not the current admin app. |

### One data service behind both apps

The apps do not keep separate competing copies of the church’s main records. They send requests to a shared backend. When an approved user submits a record, the backend checks the user, their role, the record’s reporting scope, and any event assignment before saving it. Pastors then access records within their own permitted scope.

This shared-service approach allows the church to build a level 1 collection app and a level 2–5 leadership app separately, while keeping common rules and records in one place. A future level 6–9 app can use the same backend without giving the current level 2–5 interface access to higher-level role management.

---

## 3. Church authority levels and what they mean in this project

The church’s agreed role score increases with authority. A **role score** represents a person’s place in the authority chain. It is different from a **program level**, which identifies where a particular meeting or report belongs. For example, a Group Pastor can oversee a Group, while a particular Sunday service report may still be a Local program report.

| Score | Church level | Place in the chain | Current or planned use |
|---:|---|---|---|
| **1** | Worker / Usher | Serves and reports at an assigned location or event | Current Field Utility user. Can collect only the data and scopes their account and assignments permit. |
| **2** | Location Pastor | Leads one local church location | Current Admin scope: local records, local oversight, worker status and transfer requests, local programs, and reports available within that location. Cannot directly remove a worker; may suspend and submit a removal request. |
| **3** | Group Pastor | Oversees locations in a Group | Current Admin scope: Group roll-ups and permitted location drill-down; reviews worker candidates; handles worker matters and event workflows within the Group. |
| **4** | Regional Pastor | Oversees Groups in a Region | Current Admin scope: regional roll-ups and lower-level drill-down; regional communication and information-sheet workflows; regional worker and event oversight. |
| **5** | State Overseer / State Pastor | Oversees the State | Current Admin scope: statewide roll-ups and permitted drill-down; state-level events and assignments; final state step for worker removal; state-targeted or lower-jurisdiction broadcasts. |
| **6** | Zonal Coordinator | Oversees a Zone | Higher-level app planned. The current data model does not yet define a complete Zone-to-church-path mapping, so zone-wide data access must remain unavailable until that mapping is designed and verified. |
| **7** | National Overseer | Oversees a Nation | Higher-level app planned; backend role exists. |
| **8** | Continental Leader / General Admin | Oversees a Continent and carries the church’s general-admin authority at that level | Higher-level app planned; backend role exists and its data scope is continent-based. |
| **9** | Super Admin / Superintendent | Highest authority, above all privileges | Higher-level app planned. The backend has a global role; the current level 2–5 admin client is not the level 9 interface. |

### What “scope” means

Scope is the part of the church whose information a person can access. A Location Pastor should not automatically see every location in the State. A Group Pastor should see the Group they oversee, not a different Group. As authority rises, the authorized area gets wider. The server checks this boundary on the data request; hiding a button in the screen is not treated as the security boundary.

The Admin app is intended to open with information summarized at the signed-in pastor’s level and allow drilling down to lower levels where that page and permission support it. It should not require leaders to start by browsing the lowest-level records when they need a Group, Region, or State overview.

### Typical responsibilities by level

- **Level 1 – Worker/Usher:** records data for the location or assigned event; checks approved workers into attendance; submits permitted reports. A worker is not automatically an app user: the person needs an approved worker record and an approved user account.
- **Level 2 – Location Pastor:** oversees the location’s people and activity, can suspend a worker and ask for formal removal review, starts transfers from the current location, and participates in local program/event management. The pastor cannot bypass the Group Pastor’s worker-removal authority.
- **Level 3 – Group Pastor:** sees the Group’s cumulative picture and can inspect locations below it; reviews worker-candidate registrations; handles or escalates worker-removal cases; participates in transfer approvals and event management for the Group.
- **Level 4 – Regional Pastor:** sees the Region’s cumulative picture and permitted Group/location detail; can publish the weekly information sheet and send scoped in-app communications; handles regional worker cases and regional event oversight.
- **Level 5 – State Overseer:** sees the State’s cumulative picture and permitted Region/Group/location detail; can manage state-level events and assignments, including event-specific Alpha Location teams; is the final in-app State authority for worker removal.

These are jurisdiction-bounded role capabilities, not a promise that every workflow is already accepted for live church operations. The pilot must confirm which actions each role should have and which require another reviewer.

---

## 4. What a location ID is and why the system uses it

A location code is a readable address for a church unit in the hierarchy. An illustrative code is:

```text
DCL-234-KW-ILR-ILE-003
```

It can be read as:

| Part | Meaning |
|---|---|
| `DCL` | Church identifier |
| `234` | Nigeria country calling code used in this identifier format |
| `KW` | Kwara State |
| `ILR` | Region |
| `ILE` | Group |
| `003` | A location within that Group |

If the selected reporting scope is a Group or Region, the code may stop at that level, for example `DCL-234-KW-ILR-ILE` for a Group. The code helps people recognize the church unit and helps the system organize information under its parent units.

There is also a technical distinction important for combined meetings: the database uses an internal unique record key for each physical location. A Group, Region, or State meeting is represented as a **reporting scope**, not by pretending that a Group or Region is a physical location. The system keeps the place where something physically happened separate from the wider church area the report represents. This reduces ambiguity in permissions and in summaries.

The location hierarchy lets the system answer questions such as “show this Region’s total” or “open the Groups within this Region,” while preserving the original location behind each local record.

---

## 5. The five anchors that make most Field Utility reports understandable

Most ordinary program reports need five basic identity anchors. A date is also recorded as the occurrence date, and some activities have an optional or required scheduled event identifier.

1. **Program domain – What broad family of church activity?**  
   Examples: Weekly Programs, Global Crusade, Retreat, Conferences, Special Programs. The domain lets reports group related activities together.
2. **Program type – What named activity inside that family?**  
   Examples: Sunday Worship Service, Workers Meeting, Leadership Development Meeting, Impact Academy, Crusade Evening, Faith Clinic. This distinguishes one kind of program from another within the same domain.
3. **Program level – At what church level was this meeting or report organized?**  
   Examples: Local, Group, Region, State. This describes the activity’s reporting jurisdiction; it does not change the submitter’s role score.
4. **Location/reporting scope – Which church unit does the report belong to?**  
   A local report is tied to its location. A Group or Region report is tied to that wider authorized scope, while its physical venue can be stored separately.
5. **Author/submitter – Which signed-in person sent the report?**  
   The server uses the authenticated account to establish who submitted the data. The client should not be allowed to claim that a different person submitted it. This supports accountability and follow-up.

### The date and event context

The report also needs its relevant service or meeting date. A scheduled event ID can link records to a particular time-bounded program or combined meeting. Scheduling is useful where workers need explicit assignments and collection windows, such as special events, Alpha/Satellite operations, or combined meetings. Routine activities should not be forced into a process that requires every local congregation to create a schedule if church policy does not require one.

### Why these anchors matter

Without these identity details, a number such as “250 people” is difficult to interpret. Was it a Sunday service or a crusade? Was it counted at one location or across a Group? Which date does it describe? Who submitted it? The anchors let reports filter and compare records consistently, help the server enforce access boundaries, and preserve a path back to the source.

### Fellowship reporting is a deliberate exception

Home Caring Fellowship reports are tied to a location and the specific fellowship, with the meeting date and authenticated submitter. They do **not** need a fabricated program domain, program type, program level, or general program event. The regular Field Utility user for the corresponding location can submit fellowship records; the system does not require a separate Fellowship app account.

---

## 6. What the Field Utility can do

The Field Utility is for entering information close to the activity. Its current screens include:

- **Population counter:** counts adults, youth, and children by male/female categories and keeps a running total. The submitted record is connected to the selected program and authorized reporting location/scope.
- **Workers attendance:** loads the approved worker roster for the signed-in worker’s location or approved event assignment. The usher marks the present workers and submits the capture. Combined meetings use an assigned broader roster when the event authorizes it.
- **Newcomer and convert intake:** records the information used for follow-up. Crusade convert capture can require an approved assignment.
- **Worker-candidate intake:** submits a potential worker to the location/group review flow. It is not the same as creating an app login.
- **Offerings:** captures the permitted fund type, payment method, amount, date/program context, and related submission details.
- **Home fellowship:** records fellowship attendance, member intake, and offering for a selected fellowship belonging to the user’s location.
- **Program information:** reads the latest published weekly information made available to the signed-in user.
- **Sync queue and settings:** shows saved items waiting to synchronize, connection/sync status, data settings, and instructions for installing the app on Android or iPhone/iPad.

### Location setup can use the signed-in worker’s location

After sign-in, the Utility retrieves the person’s approved worker and assigned location from the server. This reduces repeated typing and helps avoid location errors. For a combined Group, Region, or State meeting, the reporting scope can differ from the worker’s home location—but the worker must have the proper approved event assignment. Editing a displayed code alone is not permission to submit for a wider area.

Where an active event assignment unambiguously applies, the Utility can load its program and reporting setup automatically. If multiple assignments overlap, the worker needs to choose the correct one. The pilot should confirm that this matches the ushers’ actual instructions at each kind of program.

---

## 7. What the Church Admin app can do

The Admin app gives leaders an online workspace for their assigned jurisdiction. Current areas include:

- **Dashboard:** scoped totals, key activity and work summaries, quick actions, and links into the relevant records.
- **Organization and locations:** view the hierarchy and locations within the signed-in leader’s authority; support organization setup and location management where permitted.
- **Workers:** search the visible worker directory; review pending worker registrations; approve or reject candidates where the signed-in level is authorized; process permitted worker actions.
- **App users:** manage user-account approval and assigned roles for approved workers within the available role boundary.
- **Programs and events:** inspect the program taxonomy, create jurisdiction-managed events where permitted, get same-level pastor approval for admin-created events, and assign field workers to event work. A pastor at the level can create and automatically approve their own level’s event; an admin-created event awaits that level pastor. Higher-level event approval is not part of the agreed workflow.
- **Reports:** view jurisdiction-scoped summaries, trends, and exports available in the current implementation.
- **Communication:** publish structured weekly information and send targeted in-app broadcasts to users in an authorized lower jurisdiction.
- **Inbox and review workflows:** find notifications, pending decisions, and worker lifecycle requests.

An event schedule can define the program/domain or type, reporting level/scope, time window, and assigned workers. It can close automatically at the end of its window or be closed earlier by an authorized organizer. It is a tool for activities that need controlled access and coordination; it should not become unnecessary work for ordinary local services.

---

## 8. Worker registration, user accounts, and Excel imports

### The normal worker-candidate route

In Field Utility, a signed-in user can open **Home → Register a Worker Candidate** (or open **Newcomer / Convert → Worker Candidate**). The candidate is associated with the signed-in user’s location. It remains pending until the Group Pastor reviews it. An approved worker can then be considered for a separate app-user account if they need to sign into the apps.

This separation is intentional: **worker record** means the person is recognized in the church’s worker register; **user account** means the person can authenticate into the software. Not every worker needs a login, and a login should point to an approved worker.

### Excel/CSV templates available in the Admin system

The Admin system has downloadable templates and an upload workflow for:

- **Church hierarchy:** Regions, Groups, and Locations, including names and selected basic details. Some codes can be generated when left blank.
- **Worker records:** names, gender, phone, email, exact location name, unit, and optional address/occupation/marital status.

For these imports, the system can validate the spreadsheet before committing it. This is faster for loading a prepared list than entering each row through a form.

**Important pilot decision:** the current bulk worker import code creates worker records in an approved state. That is different from the regular Field Utility candidate flow, which waits for Group Pastor review. Church leadership should confirm who may use bulk import and whether imported workers should instead enter the approval queue.

The current repository provides hierarchy and worker templates; it does **not** show a bulk Excel upload that creates app-user login accounts. User accounts remain a separate workflow after the worker record exists and is approved. Do not describe the worker spreadsheet as a bulk user-account uploader.

---

## 9. What happens when several ushers submit for the same program?

The answer depends on the type of record. A unique ID on each offline item helps the system recognize a retry of the *same item*. It does not automatically know whether two different ushers counted the same people.

### Population counts: not automatically merged or deduplicated

At present, separate population submissions are stored as separate records. If two ushers submit different count records for the same event and location, the system does not infer whether the counts represent separate sections or duplicate counts of the same congregation. Reporting may total records in a scope, but it cannot reliably detect overlapping human counts from different submitters.

**Operational recommendation for the pilot:** either designate one person to submit the final location total, or explicitly divide the venue into non-overlapping counting areas and agree how those subtotals are combined. Do not ask multiple ushers to count the entire same congregation and assume the software will reconcile it.

### Workers attendance: checks for overlapping worker records

Attendance capture stores a parent submission with the present roster and creates reportable worker-level attendance rows. For a given meeting scope, the backend checks for worker attendance already recorded and rejects an overlapping capture rather than counting the same worker twice. Each submission is also linked to the signed-in submitter and event assignment when applicable.

This difference—population headcount versus named worker attendance—should be clearly explained to ushers during training.

---

## 10. Security: protections already in the system

Security is a set of safeguards working together; no single item makes an application “unhackable.” The current code and development configuration include several useful safeguards:

- **Password protection:** passwords are checked against bcrypt hashes. Bcrypt is a one-way password-checking method: the database stores a deliberately costly hash, not a readable password. The system does not need to decrypt a password to verify it.
- **Signed login tokens:** after authentication, the API uses signed tokens to recognize requests. Refresh tokens are tracked, rotated when used, and can be revoked. A password change revokes stored refresh tokens, but already issued short-lived access tokens may last until they expire.
- **Role and permission checks:** roles determine the maximum actions available. The server checks permission and hierarchy scope for protected operations; it does not trust the menu shown by the browser.
- **Church hierarchy checks:** records carry organizational paths so requests can be limited to the user’s location, Group, Region, State, Nation, Continent, or global scope as supported.
- **Database row protections:** PostgreSQL row-level security policies are present in the development database migrations and are intended as a second boundary around rows. The exact least-privilege database role and policies still need confirmation in the target hosted deployment.
- **Audit and history:** important records and actions include timestamps/actors; many operational records use soft deletion (marked inactive/deleted rather than immediately erased), which supports review and recovery. Retention policy still needs church approval.
- **Safer synchronization:** offline records use stable client-generated IDs. Replaying the same item after a timeout can be recognized as a duplicate instead of silently creating another copy. Independent records are still independent submissions.
- **Validation and throttling:** API schemas validate submitted fields and counts; some authentication routes use request throttling. Current throttling is process-local, so deployment with multiple app replicas needs a shared gateway/store control.
- **Restricted event access:** special event data can be limited by approved assignment and collection window. A worker cannot authorize a wider reporting scope merely by editing a form.

### Limits to state honestly

The security documentation records outstanding operational work: verify the target host uses the restricted runtime database account; confirm secret handling, backups/restore, and alerts; configure a dependable password-reset delivery channel; and review multi-replica rate limiting and session revocation. The Field Utility also stores offline queues on the device, so device screen-locking, shared-device practice, and clearing submitted local records matter. Application-level encryption of every stored field has not been established by this review; hosting/database encryption settings must be verified separately.

---

## 11. Data privacy and Nigerian data-protection responsibilities

The apps process personal information such as names, phone numbers, email addresses, worker units, location, and—in some flows—address or follow-up information. Even a church system must explain why information is collected, limit it to what is needed, restrict access, keep it accurate, retain it only as long as justified, and have a process for people’s privacy requests and data incidents.

The **Nigeria Data Protection Act 2023** requires appropriate technical and organisational measures to protect personal data. The Act identifies measures that may include encryption, resilience and recovery, risk assessment, and regular testing. It also requires a prior data-protection impact assessment when processing is likely to create high risk to people’s rights and freedoms. See the [official Nigeria Data Protection Act 2023](https://ndpc.gov.ng/wp-content/uploads/2024/03/Nigeria_Data_Protection_Act_2023.pdf), including Sections 28–29 and 39–40, and the [Nigeria Data Protection Commission’s resources](https://ndpc.gov.ng/resources/).

**This project brief does not claim legal certification or a completed NDPC compliance audit.** Technical safeguards help, but compliance also depends on church decisions and operational practice. Before live personal data is used, stakeholders should confirm:

1. Which church body is the data controller and which hosting/service providers act as processors.
2. The lawful basis and clear privacy notice for each category of information, including worker, newcomer/convert, and children-related information.
3. Which fields are truly necessary. Avoid collecting sensitive notes or detailed personal stories unless there is a clear approved purpose and protection plan.
4. Who can see each kind of record, how a person can request correction/access, and how records are retained or erased.
5. Whether the planned processing requires a Data Protection Impact Assessment and any NDPC registration or other formal steps applicable to the church.
6. How breach response, backup recovery, staff training, and hosting-provider agreements will work.

For a final compliance determination, the church should consult its designated data-protection lead or a qualified Nigerian privacy professional. Compliance depends on governance and hosting arrangements as well as code.

---

## 12. Why use a PWA instead of only a website or separate native apps?

A **Progressive Web App (PWA)** is a website built with app-like capabilities. People open it in a browser and can optionally add it to their phone or computer’s home screen. It is still web software; it is not an Android APK or an iPhone App Store application.

| Option | What it means | Fit for this project |
|---|---|---|
| Ordinary website | Open a page in a browser; usually needs a live connection for each action | Useful for the Admin app and reporting, but insufficient by itself for field work where connection may be unreliable. |
| PWA | Browser-based app that can be installed to the home screen and can cache its app shell and queue selected work locally | One shared Field Utility experience for Android, iPhone/iPad, and laptops; avoids separate app-store releases and supports offline capture-and-sync workflows. |
| Native mobile app | Separate platform-specific Android/iOS apps distributed through stores or installation packages | Can use deeper device features, but requires separate builds, review/release processes, and platform maintenance. It may be considered later if operational needs justify it. |

The PWA approach is practical for a distributed church workforce: an usher can use a browser link, install the same app on a supported phone, and use a laptop when appropriate. On Android, a compatible browser may show an install prompt. On iPhone/iPad, the user adds it from Safari’s Share menu. The app can save supported work locally and send it after the connection returns.

Offline support is not the same as unlimited offline access. The device must have opened/installed the app and signed in before; some screens need a connection to load current information. Browser and operating-system behavior differs, and locally queued data remains on that device until synchronized or cleared. External SMS or push notification delivery is not currently implemented; the Admin communications currently appear through authenticated in-app channels.

---

## 13. Technology, explained without requiring a technical background

| Technology | Plain-language role |
|---|---|
| **Python** | Main programming language used for the backend and much of the user-interface code. |
| **FastAPI** | Web framework that receives requests, validates them, applies rules, and returns data to the apps. Think of it as the service desk between the apps and the database. |
| **FastHTML and FastStrap** | Tools used to build the browser pages and reusable interface components. |
| **PostgreSQL** | The relational database that stores structured church records and the links between them. The development database is hosted through Supabase/PostgreSQL. |
| **JavaScript, browser storage, and service worker** | Power interactive Field Utility screens, keep selected work in a local queue, cache app files, and synchronize records when the network is available. |
| **Bcrypt and signed tokens** | Help verify passwords without storing them in readable form and help the backend recognize authenticated requests. |

The technology is an implementation choice. The stakeholder questions that matter most are whether the screens match real church work, reports are accurate, approvals are correct, and data is protected.

---

## 14. Current project stage and known limitations

As of this brief, the repositories have recent development releases (Church Admin/Server **1.4.1** and Field Utility **1.1.1**). The project has been exercised with development records, local API/database flows, and browser checks. Some implementation phases have local acceptance; comprehensive release acceptance is still open.

### Progress already made

- Canonical role scores and the level 2–5 administrative boundary have been aligned with the agreed 1–9 chain.
- Program domains/types, event/reporting scope metadata, and field submission contracts have been normalized in the development work.
- Worker-candidate approval, suspension/removal review, and transfer workflow logic have been implemented and migrated in the development environment.
- Field Utility offline queues and backend synchronization include duplicate-retry handling; aggregate workers-attendance submission has a parent record and linked worker records.
- Combined-meeting scheduling, approval, assignment, attendance collection, and auto-setup have been exercised locally.
- Weekly information sheets and scoped in-app broadcasts have been exercised locally.
- The Field Utility has been connected to the Admin/backend integration path and has Android/iOS installation instructions.

### Not yet proven as production-ready

- The implementation plan still lists Phase 7 acceptance as open: exhaustive tests for cross-jurisdiction access, full hosted integration against the exact deployed backend, multi-event Alpha/Satellite and Crusade/Retreat scenarios, phone testing, operational monitoring, and stakeholder sign-off.
- A previous development check found the hosted API did not yet persist the new metadata contract correctly, while the updated local backend did. The hosted backend and Utility must therefore be confirmed to run compatible releases before presenting hosted behavior as verified.
- The six demographic count categories and labels, program taxonomy, role titles, event and transfer approval routes, report definitions, and exception handling need review by people who know the church’s actual operations.
- Multiple population-count submissions for the same location/event are not automatically merged or checked for overlapping audience coverage.
- Bulk worker import currently approves imported worker records and is not the ordinary Group Pastor candidate-review path. Bulk user-account upload is not present in the current code.
- Pastor-managed fine-grained delegation of selected permissions to individual workers has been discussed but is not implemented. Current role permissions remain the baseline.
- External push/SMS notifications, production privacy/legal sign-off, and full production deployment controls are not claimed complete.

For presentation: call this a **working development system in pilot and refinement**, not a fully deployed national production system. A successful local demonstration proves the demonstrated local workflow, not every hosted device, account, report, or production control.

---

## 15. The feedback needed from church stakeholders

The project team needs operational decisions and corrections more than technical vocabulary. Please focus on:

### Church structure and names

- Are the level names and boundaries correct: Location, Group, Region, State, Zone, Nation, Continent, and Global?
- Do the human-readable location codes match the codes people actually use? What are the authoritative codes and parent relationships?
- Are all church types/branches represented correctly?

### Programs and reporting

- Are the five domains and their program types complete and named correctly?
- Which routine programs must be scheduled, and which should work without a schedule?
- For each program, what is the reporting level, date/time rule, and location/scope rule?
- For a combined meeting, who is the physical host and who is authorized to submit for the wider Group/Region/State?
- For Crusades and Retreats, who designates the Alpha Location, satellite reporters, data types, and event windows?
- Should count submissions from several ushers be partitioned and totalled, or should one designated usher submit the final total?
- Which population categories, gender labels, and age-group definitions should be used?

### Worker and user workflows

- Who may submit a worker candidate, and who approves it? Is Group Pastor approval always required?
- Should bulk-imported workers enter the same approval queue instead of becoming approved immediately?
- Who may create app accounts, assign roles, suspend access, and approve new users?
- Confirm the worker transfer chain, including the receiving Location Pastor and receiving Group Pastor approvals and Regional review.
- Confirm who suspends, removes, or escalates worker discipline cases at each level.

### Privacy and communications

- Which personal details are genuinely needed for workers, newcomers/converts, and follow-up?
- Who may view each detail, and for how long should it be kept?
- Who owns and approves weekly information sheets and broadcasts at each level?
- Is in-app communication sufficient for the pilot, or is SMS/push delivery a later requirement?

---

## 16. Likely stakeholder questions

### “Will every pastor see every church record?”

No. Access is scoped to the pastor’s authorized level and hierarchy. A Location Pastor works within the location; a Group Pastor within the Group; a Regional Pastor within the Region; and a State Overseer within the State. Higher roles have broader scopes. The system should show cumulative summaries at the leader’s level and support permitted drill-downs.

### “Does a program level of Region make the signed-in user a Regional Pastor?”

No. Program level describes the meeting/report. A user’s role score describes that person’s authority. A location worker can submit for a Region-level meeting only through the explicit authorization and assignment path, not by changing a dropdown.

### “Can a worker use the system without an account?”

They can be stored as a worker without a login. To sign into Field Utility or Admin, they need a linked approved user account. Access is not granted just because a person’s details appear in an Excel file.

### “Can the field app work without internet?”

It can save supported records on the device and synchronize them later. The app still needs connectivity for some current server data, and offline queues need careful handling on shared or lost devices.

### “Does the system add two ushers’ counts together and know they are correct?”

It stores separate count submissions and can total data for reports, but it cannot currently determine whether two ushers counted the same people. The church needs a counting protocol, such as one final submitter or non-overlapping counting areas.

### “Can the State Overseer send a message to just one Group?”

Scoped in-app broadcasts are implemented in the development work for authorized downward targeting. External push notifications and SMS are not included at this stage.

### “Is this already compliant with data protection law?”

The software includes security controls that support responsible handling, but no completed legal compliance audit or certification is claimed. The church must confirm its lawful purposes, privacy notice, data retention, user rights process, hosting agreements, and any required impact assessment with its privacy lead.

### “Why not build one giant app for everyone?”

Different users have different daily tasks and authority. Field workers need fast, simple, phone-friendly capture; pastors need review, approvals, communication, and analytics; national or global leaders need a different, broader product. Separate clients make the experience clearer while a shared backend keeps identity, data, and permission rules consistent.

---

## 17. Future higher-level app: levels 6–9

The present Admin app is for levels 2–5. When the church is ready, a separate higher-level client can present the broader views needed by:

- **Level 6 – Zonal Coordinator:** zone totals and drill-down once a formal Zone structure is represented in the database.
- **Level 7 – National Overseer:** national roll-ups, comparisons between States, and national programs/communications.
- **Level 8 – Continental Leader / General Admin:** continent-wide oversight and cross-national summaries within the assigned continent.
- **Level 9 – Super Admin / Superintendent:** global administration, oversight, and the highest authority functions.

The future app should be designed around the decisions these leaders make, not merely expose a larger list of lower-level records. Its dashboards should begin with the appropriate cumulative view and allow controlled drill-down. It should receive its own stakeholder design and authorization review when that project begins. The existing shared backend’s role grants are not equivalent to a completed higher-level user interface or verified zone-wide scope.

---

## 18. Suggested opening statement for the presentation

> “This project connects field data collection with pastoral oversight. Workers use one phone-friendly app to record church activity, attendance, and follow-up information. Pastors use a separate app to see the records for their location, Group, Region, or State, review requests, manage programs, and communicate downward. The system is being refined with church leaders now so that the labels, approvals, data rules, and reports match how Deeper Life actually operates before we treat it as a production service.”

---

## 19. Project references

- [Comprehensive project review](COMPREHENSIVE_PROJECT_REVIEW.md)
- [Implementation fix plan and phase status](IMPLEMENTATION_FIX_PLAN.md)
- [System overview](docs/OVERVIEW.md)
- [Security controls and open deployment work](docs/SECURITY.md)
- [Nigeria Data Protection Act 2023 – NDPC official copy](https://ndpc.gov.ng/wp-content/uploads/2024/03/Nigeria_Data_Protection_Act_2023.pdf)
- [Nigeria Data Protection Commission resources](https://ndpc.gov.ng/resources/)


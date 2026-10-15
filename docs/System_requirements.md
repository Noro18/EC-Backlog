# System Requirements — Configuration Specification (EC) Backlog Management System

*Timor Telecom — Draft — Internal Use TT — Translated to English for reference*

| Field | Value |
|---|---|
| Document title | System Requirements — Configuration Specification (EC) Backlog Management System |
| Version | 1.1 |
| Date | September 23, 2026 |
| Author | Marquese |
| Team / Area | DDS/SDS |
| Classification | Internal use |
| Reference document | Numeracao_EC_2026_v_1_0.xlsx |

> **Note:** This is an English translation of the original Portuguese document, prepared for reference and comprehension purposes. In case of any discrepancy, the original Portuguese version prevails.

---

## Version History

| Version | Date | Prepared/Reviewed/Approved | Description of change |
|---|---|---|---|
| 1.0 | 09-22-2026 | marquese/laya | Initial version of the document, prepared based on the description of the current process and the requirements for the new system. |
| 1.1 | 09-22-2026 | marquese/laya | Added version control for the EC document. |

---

## 1. Introduction

### 1.1. Purpose

This document specifies the functional and non-functional requirements for the development of a new backlog management system, intended to replace the currently manual process of assigning identifiers and controlling the lifecycle of Configuration Specifications (EC) at TT.

The system aims to automate the generation of identifiers (EC ID and Release ID), the recording of relevant dates, document uploads, and the approval workflow between the requester, the CD (Department Head), and the DES team — currently managed manually and across scattered channels (Excel and email).

### 1.2. Scope

The functional scope of this document includes:

- Automatic generation of the EC ID and the Release identifier;
- Recording of the specification's creation date and its production go-live date;
- Uploading of the specification document into the system;
- Assignment of the specification to a CD for validation and approval;
- Automatic email notification to the CD;
- Return of the approval decision to the originating team;
- Version control for the EC document;
- Routing of the approved specification to the DES team, through the system.

The following are out of scope for this document and should be handled in a later phase or by another team (to be confirmed): the technical development and implementation of configuration changes by the DDS team, and the management of testing associated with deployment.

### 1.3. Definitions, Acronyms and Abbreviations

The following terms were identified from the provided numbering file (Numeracao_EC_2026_v_1_0.xlsx).

| Term | Description |
|---|---|
| EC | Configuration Specification — the document and corresponding identifier that records a change to the configuration of TT's systems. |
| EC ID | Sequential identifier, assigned per calendar year, that uniquely identifies each EC. |
| ME | Evolutionary Maintenance — naming convention used until 2025 to reference the originating request for the EC. |
| CR | Change Request — naming convention adopted from 2026 onward to reference the originating request for the EC, replacing "ME". |
| RT | Request Ticket — reference to an incident or request ticket registered in another system. |
| COR | Correction — an EC created to correct a previous release. |
| Release | A set of configuration changes deployed together to Production, identified in the format `TT_ON_AAAA-NNN`. |
| PRD | Production environment. |
| DDS | Development Team, responsible for the technical implementation of approved changes (to be confirmed). |
| CD | Department Head — responsible for validating and approving (or rejecting) the specification. |
| Backlog | Centralized, ordered list of all ECs, with their respective status in the lifecycle. |

---

## 2. Current Situation ("As-Is" Process)

### 2.1. Description of the Current Process

Currently, the process of creating and approving an EC is carried out manually, through the following steps:

- The EC ID is created manually in an Excel spreadsheet, with sequential numbering per calendar year.
- The configuration change specification (document) is drafted.
- The document is sent to the CD outside the system (typically by email) for validation and approval.
- After approval, the document is sent to the DES team.

The file `Numeracao_EC_2026_v_1_0.xlsx`, provided as a reference, contains one sheet per year (2019 to 2026) with the historical record of ECs, including — depending on the year — columns such as: EC ID, ME/RT or CR/RT reference, Description, Release, and Production go-live date.

### 2.2. Limitations of the Current Process

- Manual numbering prone to errors, duplication, and format inconsistencies — for example, variations in the Release identifier format over the years ("Release TT_ON_2020-000", "TT-ON-2021-028", "TT_ON_2022-001", "TT_ON_2026 - 001").
- No centralized, automatic record of each EC's approval status.
- Approvals managed outside the system (email), with no auditable, centralized history.
- Lack of automatic traceability between the EC ID, its associated Release, and the production go-live date.
- Dependency on continuous manual updates to the spreadsheet, with a risk of it becoming outdated.
- Difficulty searching and consulting the full history (multiple sheets, one per year, with no consolidated view).

---

## 3. Overview of the Proposed Solution ("To-Be")

The new system must centralize, in a single location, the creation, numbering, approval, and routing of ECs, eliminating the manual steps currently carried out in Excel and by email. In summary, the system must:

- Automatically assign the EC ID and the Release ID;
- Record the creation date and the production go-live date;
- Allow the specification document to be uploaded;
- Allow the specification to be assigned to a CD for approval, with automatic email notification;
- Automatically return the approval decision to the team;
- Allow version control of the EC document, enabling the upload of new versions if the specification is rejected for correction, while preserving the history and traceability of previous versions;
- Allow the approved EC to be routed to the DES team, without leaving the system.

---

## 4. System Actors

| Actor | Responsibilities |
|---|---|
| Requester | Creates the specification in the system, uploads the document, and assigns the specification to a CD for approval. |
| Department Head (CD) | Receives the notification, reviews the specification, and records the approval or rejection decision (with comments) in the system. |
| DES Team | Receives, through the system, the approved specifications for technical implementation in Production. |
| System Administrator | Manages users, access profiles, and numbering parameters (need for a dedicated profile to be confirmed). |
| System | Automates the generation of identifiers and dates, the sending of notifications, and the history/audit log. |

---

## 5. Functional Requirements

The table below consolidates the functional requirements identified from the process described, organized in approximate order of execution within the process flow (see Section 6).

| ID | Requirement | Description |
|---|---|---|
| RF01 | Automatic generation of the EC ID | The system must automatically generate a unique, sequential identifier (EC ID) for each new specification submitted, eliminating manual assignment in Excel. Numbering must follow the convention observed in the history (sequential, per calendar year). Each EC can be associated with an already-open Release. |
| RF02 | Automatic generation/association of the Release ID | The system must automatically generate, or allow association with an existing open Release, the Release identifier in the format `TT_ON_AAAA-NNN`. A Release can group more than one EC, as observed in the history, so the system must support a one-to-many relationship between Release and EC. |
| RF03 | Recording of the Creation Date | The specification's creation date must be recorded by the user at the moment of submission. |
| RF04 | Recording of the Production Go-Live Date | The system must allow recording of the date on which the corresponding Release is implemented in Production (equivalent to the "PRD entry date" field in the current process). This entry is made manually. |
| RF05 | Version control of the EC document | The system must allow version control of the EC document. In case of rejection, the Requester must be able to correct and attach a new version of the document, keeping the same EC ID. The system must automatically increment the version (e.g., v1.0, v1.1, v2.0), keep the full history of previous versions, and ensure traceability of changes. |
| RF06 | Document upload | The system must allow the requester to upload the specification document (e.g., .docx, .pdf) associated with the generated EC ID. |
| RF07 | Assignment of the specification to a CD | After the document is uploaded, the system must present the option to assign the specification to a CD responsible for validation and approval. |
| RF08 | Automatic email notification | When the specification is assigned, the system must automatically send an email notification to the designated CD, informing them that validation is needed. |
| RF09 | Recording of the approval or rejection decision | The system must allow the CD to approve or reject the specification directly in the system. In case of rejection, the CD must record a comment with the reason, which is returned to the requester/team (see RF10); the specification can then be corrected and resubmitted by the same requester. |
| RF10 | Return of the decision to the team | After the CD's decision (approval or rejection), the system must automatically notify the originating requester/team of the validation result, including the comment in case of rejection. |
| RF11 | Routing to the DES team | Once approved, the requester must be able to route the specification, through the same system, to the DES team, preserving the history and traceability of the process. Routing automatically closes the EC. When all ECs in a Release are closed, the Release closes automatically. The CD's role ends at approval/rejection (RF09). |
| RF12 | Consultation and search (backlog) | The system must provide a backlog view, with search and filtering by EC ID, Release, Status, date, and requester, replacing the current Excel spreadsheet and consolidating the history of all years. |

> **Note:** In the original document, RF10 is numbered "RF010"; it is treated here as RF10 for consistency.

---

## 6. Process Flow ("To-Be")

The proposed flow for the new system is as follows:

1. The requester creates a new specification in the system.
2. The system automatically assigns the EC ID and generates/associates the Release ID (RF01, RF02).
3. The requester records the Creation Date at the moment of submission (RF03).
4. The requester uploads the specification document (RF06).
5. The requester assigns the specification to a CD (RF07).
6. The system notifies the CD by email (RF08).
7. The CD reviews the document and records the decision — approval or rejection — in the system (RF09).
8. The system automatically notifies the requester/team of the decision (RF10).
9. If approved, the requester routes the specification to the DES team through the system, which automatically closes the EC. When all ECs in a Release are closed, the Release closes automatically (RF11).
10. If rejected, the CD records a comment with the reason for rejection, and the specification is returned to the requester/team (RF09, RF10).
11. The requester corrects the specification and uploads a new version of the document to the system. The system automatically increments the version and preserves the history of previous versions (RF05). The flow returns to step 5 for reassignment to a CD.
12. After all ECs are closed and the Release closes, the requester records the Production Go-Live Date on the closed Release in the system (RF04).
13. The EC status is updated in the backlog (RF11).

---

## 7. Data Structure

The following fields were identified from the described process and the existing history in the file `Numeracao_EC_2026_v_1_0.xlsx`, complemented with the status and audit fields required for the new approval workflow.

| Field | Description | Source |
|---|---|---|
| EC ID | Unique sequential identifier, generated automatically. | Automatic |
| ME / RT / CR Reference | Reference to the originating request (Modification, incident ticket, or Change Request). | Manual |
| Description | Text description of the configuration change. | Manual |
| Release ID | Identifier of the associated production Release (format `TT_ON_AAAA-NNN`). | Automatic / Association |
| Creation Date | Date the specification was submitted in the system. | Automatic |
| Production Go-Live Date | Date the Release was implemented in the Production environment. | Manual |
| Status | Lifecycle status: In Validation, Approved, Rejected, Sent to DES, Closed, Cancelled. | Automatic (transitions) |
| Requester | User who submitted the specification. | Automatic (session) |
| Responsible CD | User assigned for validation and approval. | Manual (selection) |
| Rejection Comment | Reason recorded by the CD when the specification is rejected. | Manual |
| Document Version | Sequential number of the current version of the specification document (e.g., v1.0, v1.1, v2.0). Automatically incremented on each new upload after rejection. | Automatic |
| Version History | List of all previous versions of the document, with upload date, user, and reason for the change, ensuring traceability. | Automatic |
| Attached Document | Specification file uploaded to the system. | Manual (upload) |
| History / Audit Log | Chronological record of actions and status transitions. | Automatic |

---

## 8. Non-Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| RNF01 | Access control | The system must support distinct profiles (Requester, CD, DES Team, Administrator), with permissions appropriate to each. |
| RNF02 | Auditing | All relevant actions (creation, assignment, approval/rejection, routing) must be recorded with user and date/time, in an immutable manner. |
| RNF03 | Notification reliability | Email notification delivery must be reliable, with a retry mechanism or alert in case of a sending failure. |
| RNF04 | Historical data migration | The system must allow the import of the existing Excel history (2019–2026), preserving the identifiers already assigned. |
| RNF05 | Usability | The interface must be simple and intuitive, without requiring extensive training for current users of the manual process. |
| RNF06 | Availability | The system must be available during the team's normal operating hours (business days, 08:00–18:00). |

---

## 9. Acceptance Criteria

- The system automatically generates the EC ID and the Release ID, without manual intervention.
- The creation date is recorded at the moment the specification is submitted.
- A document can be uploaded and assigned to a CD through the system.
- The CD receives an email notification at the moment a specification is assigned to them.
- The CD's decision (approval or rejection, with comment) is automatically communicated to the originating requester/team.
- In case of rejection, the system allows the requester to upload a new version of the document, keeping the same EC ID, automatically incrementing the version, and preserving the history of previous versions.
- An approved specification can be routed to the DES team through the system.
- The production go-live date can be recorded manually in the system, associated with the corresponding Release.
- The history of all ECs, including historical data from 2019–2026, is available and searchable in the system.

---

## Annex A — Sample of the Current Numbering (EC 2026)

Illustrative excerpt, based on the "2026" sheet of the file `Numeracao_EC_2026_v_1_0.xlsx`, included as a reference for the data format currently in use.

| EC ID | CR/RT/COR | Description | Release | PRD Go-Live Date |
|---|---|---|---|---|
| 1 | CR2026003 | Changes to GPON Internet Offers — Phase 1 | TT_ON_2026-001 | 01-23-2026 |
| 2 | RT No. 29411 | Notification anomaly regarding sign-up and profile change for the Ready service | TT_ON_2026-001 | 01-23-2026 |
| 3 | CR2026005 | Daily Limit Change for the Unlimited Net Light (UNL) Package | TT_ON_2026-003 | — |
| 6 | CR2026011 | 50% bonus on data allowances for new plans | TT_ON_2026-004 | 02-13-2026 |
| 7 | COR2026001 | Correction to release TT_ON_2026-004 | TT_ON_2026-005 | 02-17-2026 |
# Extra Diagrams

## Offerings Lifecycle
```mermaid
sequenceDiagram
  participant User
  participant API
  participant DB
  User->>API: POST /offerings
  API->>DB: create offering (pending)
  API-->>User: OfferingResponse
```

## Counts Lifecycle
```mermaid
sequenceDiagram
  participant Usher
  participant API
  participant DB
  Usher->>API: POST /counts
  API->>DB: create count
  API-->>Usher: CountResponse
```

## Attendance Lifecycle
```mermaid
sequenceDiagram
  participant Leader
  participant API
  participant DB
  Leader->>API: POST /attendance
  API->>DB: create attendance
  API-->>Leader: AttendanceResponse
```

## Newcomer/Convert Flow
```mermaid
sequenceDiagram
  participant Usher
  participant API
  participant DB
  Usher->>API: POST /records
  API->>DB: create record (pending)
  API-->>Usher: RecordResponse
```

## Announcement Publishing
```mermaid
sequenceDiagram
  participant Admin
  participant API
  participant DB
  Admin->>API: POST /announcements
  API->>DB: create announcement
  API-->>Admin: AnnouncementResponse
```

## User Creation Flow
```mermaid
sequenceDiagram
  participant Admin
  participant API
  participant DB
  Admin->>API: POST /workers
  API->>DB: create worker
  Admin->>API: POST /users
  API->>DB: create user
  API-->>Admin: UserResponse
```

## Fellowship Activity Flow
```mermaid
sequenceDiagram
  participant Leader
  participant API
  participant DB
  Leader->>API: POST /fellowships/members
  API->>DB: add member
  Leader->>API: POST /fellowships/attendance
  API->>DB: add attendance
  Leader->>API: POST /fellowships/offerings
  API->>DB: add offering
  API-->>Leader: success
```


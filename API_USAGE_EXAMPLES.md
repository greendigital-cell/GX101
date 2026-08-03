# BRD Normalize API Usage Examples

## Base URL
```
http://localhost:8001/api/normalize
```

## 🆕 NEW: Add BRD by GSolve Project ID

**Endpoint:** `POST /api/normalize/add-brd-by-project`

This endpoint automatically fetches project details from GSolve API and associates the BRD with that project.

**Request Body:**
```json
{
  "brd_title": "BRD HRM Employee Registration",
  "project_id": 1,
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "In Review",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    },
    {
      "source_ref": "BRD-S3.2.2",
      "clause_statement": "The system shall track approvals and status changes.",
      "page": 13,
      "type_suggestion": "Functional",
      "status": "Normalised",
      "section": "3.2 Task Management",
      "extracted_keywords": ["track approvals", "status changes"]
    }
  ]
}
```

**Response:**
```json
{
  "message": "BRD data added successfully with GSolve project details",
  "brd_id": "6a70c844f7bc4b4a7c24c166",
  "total_clauses": 2,
  "status_counts": {
    "All": 2,
    "Unprocessed": 0,
    "In Review": 1,
    "Normalised": 1,
    "Needs Clarification": 0
  },
  "project_details": {
    "gsolve_project_id": 1,
    "project_code": "GSolve",
    "project_name": "GREEN GSolve",
    "customer": "GREEN Limited",
    "start_date": "31-Mar-2024",
    "target_end_date": "30-Aug-2024",
    "project_manager": "John Doe"
  }
}
```

**cURL Example:**
```bash
curl -X 'POST' \
  'http://127.0.0.1:8001/api/normalize/add-brd-by-project' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "brd_title": "BRD HRM Employee Registration",
  "project_id": 1,
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "In Review",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    }
  ]
}'
```

---

## 🆕 Get BRDs by Project ID

**Endpoint:** `GET /api/normalize/get-brds-by-project/{project_id}`

Get all BRDs associated with a specific GSolve project.

**Example:**
```
GET http://localhost:8001/api/normalize/get-brds-by-project/1?skip=0&limit=10
```

**Response:**
```json
{
  "total": 5,
  "skip": 0,
  "limit": 10,
  "project_id": 1,
  "data": [
    {
      "id": "6a70c844f7bc4b4a7c24c166",
      "brd_title": "BRD HRM Employee Registration",
      "gsolve_project_id": 1,
      "project_code": "GSolve",
      "project_name": "GREEN GSolve",
      "customer": "GREEN Limited",
      "total_clauses": 2,
      "status_counts": {...},
      "created_at": "2026-08-03T10:30:00"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/api/normalize/get-brds-by-project/1?skip=0&limit=10' \
  -H 'accept: application/json'
```

---

## 🆕 Get ALL Normalized BRDs by Project ID (Complete Summary)

**Endpoint:** `GET /api/normalize/get-all-normalize-brds-by-project/{project_id}`

Get all normalized BRD data for a specific project with complete status breakdown across all BRDs.
This endpoint returns:
- All BRDs for the project
- Overall status counts across all BRDs
- Individual BRD summaries with clauses grouped by status

**Example:**
```
GET http://localhost:8001/api/normalize/get-all-normalize-brds-by-project/1
```

**Response:**
```json
{
  "message": "BRDs fetched successfully",
  "project_info": {
    "project_id": 1,
    "project_code": "GSolve",
    "project_name": "GREEN GSolve",
    "customer": "GREEN Limited"
  },
  "total_brds": 3,
  "overall_status_counts": {
    "all": 50,
    "unprocessed": 10,
    "in_review": 15,
    "normalised": 20,
    "needs_clarification": 5
  },
  "brds": [
    {
      "brd_id": "6a70c844f7bc4b4a7c24c166",
      "brd_title": "BRD HRM Employee Registration",
      "project_id": 1,
      "project_code": "GSolve",
      "project_name": "GREEN GSolve",
      "customer": "GREEN Limited",
      "created_at": "2026-08-03T10:30:00",
      "updated_at": "2026-08-03T10:35:00",
      "status_counts": {
        "all": 20,
        "unprocessed": 4,
        "in_review": 6,
        "normalised": 8,
        "needs_clarification": 2
      },
      "clauses_by_status": {
        "all": [...],
        "unprocessed": [...],
        "in_review": [...],
        "normalised": [...],
        "needs_clarification": [...]
      }
    },
    {
      "brd_id": "6a70c844f7bc4b4a7c24c167",
      "brd_title": "BRD Task Management System",
      "project_id": 1,
      "project_code": "GSolve",
      "project_name": "GREEN GSolve",
      "customer": "GREEN Limited",
      "created_at": "2026-08-03T11:00:00",
      "updated_at": "2026-08-03T11:05:00",
      "status_counts": {
        "all": 30,
        "unprocessed": 6,
        "in_review": 9,
        "normalised": 12,
        "needs_clarification": 3
      },
      "clauses_by_status": {
        "all": [...],
        "unprocessed": [...],
        "in_review": [...],
        "normalised": [...],
        "needs_clarification": [...]
      }
    }
  ]
}
```

**cURL Example:**
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/api/normalize/get-all-normalize-brds-by-project/1' \
  -H 'accept: application/json'
```

**Key Features:**
- ✅ Returns ALL BRDs for a project (no pagination)
- ✅ Overall status counts aggregated across all BRDs
- ✅ Individual BRD summaries with status breakdown
- ✅ All clauses grouped by status for each BRD
- ✅ Project information included

---

## 🆕 Get BRD Summary with Status Counts

**Endpoint:** `GET /api/normalize/get-brd-summary/{brd_id}`

Get complete BRD data with all clauses grouped by status and counts for each category.

**Example:**
```
GET http://localhost:8001/api/normalize/get-brd-summary/6a70c844f7bc4b4a7c24c166
```

**Response:**
```json
{
  "brd_id": "6a70c844f7bc4b4a7c24c166",
  "brd_title": "BRD HRM Employee Registration",
  "project_code": "GSolve",
  "project_name": "GREEN GSolve",
  "gsolve_project_id": 1,
  "customer": "GREEN Limited",
  "created_at": "2026-08-03T10:30:00",
  "updated_at": "2026-08-03T10:35:00",
  
  "status_counts": {
    "all": 36,
    "unprocessed": 6,
    "in_review": 8,
    "normalised": 18,
    "needs_clarification": 4
  },
  
  "clauses_by_status": {
    "all": [...],
    "unprocessed": [...],
    "in_review": [...],
    "normalised": [...],
    "needs_clarification": [...]
  }
}
```

**cURL Example:**
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/api/normalize/get-brd-summary/6a70c844f7bc4b4a7c24c166' \
  -H 'accept: application/json'
```

---

## 🆕 Get BRD Clauses by Specific Status

**Endpoint:** `GET /api/normalize/get-brd-clauses-by-status/{brd_id}?status={status}`

Get clauses filtered by specific status with count.

**Status Options:**
- `all` - All clauses
- `unprocessed` - Unprocessed clauses
- `in_review` - In Review clauses
- `normalised` - Normalised clauses
- `needs_clarification` - Needs Clarification clauses

**Examples:**
```
GET http://localhost:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=all
GET http://localhost:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=unprocessed
GET http://localhost:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=in_review
GET http://localhost:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=normalised
GET http://localhost:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=needs_clarification
```

**Response:**
```json
{
  "brd_id": "6a70c844f7bc4b4a7c24c166",
  "brd_title": "BRD HRM Employee Registration",
  "project_code": "GSolve",
  "project_name": "GREEN GSolve",
  "status_filter": "unprocessed",
  "total_count": 6,
  "clauses": [...]
}
```

**cURL Examples:**
```bash
# Get all clauses
curl -X 'GET' 'http://127.0.0.1:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=all' -H 'accept: application/json'

# Get unprocessed
curl -X 'GET' 'http://127.0.0.1:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=unprocessed' -H 'accept: application/json'

# Get in review
curl -X 'GET' 'http://127.0.0.1:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=in_review' -H 'accept: application/json'

# Get normalised
curl -X 'GET' 'http://127.0.0.1:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=normalised' -H 'accept: application/json'

# Get needs clarification
curl -X 'GET' 'http://127.0.0.1:8001/api/normalize/get-brd-clauses-by-status/6a70c844f7bc4b4a7c24c166?status=needs_clarification' -H 'accept: application/json'
```

---

## 1. Add BRD Data

**Endpoint:** `POST /api/normalize/add-brd`

**Request Body:**
```json
{
  "brd_title": "BRD HRM Employee Registration",
  "project_code": "PROJ-001",
  "project_name": "HR Management System",
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "In Review",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    },
    {
      "source_ref": "BRD-S3.2.2",
      "clause_statement": "The system shall track approvals and status changes.",
      "page": 13,
      "type_suggestion": "Functional",
      "status": "Normalised",
      "section": "3.2 Task Management",
      "extracted_keywords": ["track approvals", "status changes"]
    },
    {
      "source_ref": "BRD-S3.2.3",
      "clause_statement": "Users shall receive notifications for overdue tasks.",
      "page": 14,
      "type_suggestion": "Functional",
      "status": "In Review",
      "section": "3.2 Task Management",
      "extracted_keywords": ["notifications", "overdue tasks"]
    },
    {
      "source_ref": "BRD-S3.2.4",
      "clause_statement": "Role-based access must be enforced.",
      "page": 15,
      "type_suggestion": "Security",
      "status": "Unprocessed",
      "section": "3.2 Task Management",
      "extracted_keywords": ["role-based access", "enforced"]
    },
    {
      "source_ref": "BRD-S3.2.5",
      "clause_statement": "System shall maintain an audit log of all task updates.",
      "page": 16,
      "type_suggestion": "Non-Functional",
      "status": "Normalised",
      "section": "3.2 Task Management",
      "extracted_keywords": ["audit log", "task updates"]
    }
  ]
}
```

**Response:**
```json
{
  "message": "BRD data added successfully",
  "brd_id": "507f1f77bcf86cd799439011",
  "total_clauses": 5,
  "status_counts": {
    "All": 5,
    "Unprocessed": 1,
    "In Review": 2,
    "Normalised": 2,
    "Needs Clarification": 0
  }
}
```

## 2. Get BRD Data by ID

**Endpoint:** `GET /api/normalize/get-brd/{brd_id}`

**Example:**
```
GET http://localhost:8001/api/normalize/get-brd/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "brd_title": "BRD HRM Employee Registration",
  "project_code": "PROJ-001",
  "project_name": "HR Management System",
  "clauses": [...],
  "total_clauses": 5,
  "status_counts": {
    "All": 5,
    "Unprocessed": 1,
    "In Review": 2,
    "Normalised": 2,
    "Needs Clarification": 0
  },
  "created_at": "2026-08-03T10:30:00",
  "updated_at": "2026-08-03T10:30:00"
}
```

## 3. Get All BRDs (with pagination)

**Endpoint:** `GET /api/normalize/get-all-brds?skip=0&limit=10`

**Example:**
```
GET http://localhost:8001/api/normalize/get-all-brds?skip=0&limit=10
```

**Response:**
```json
{
  "total": 25,
  "skip": 0,
  "limit": 10,
  "data": [
    {
      "id": "507f1f77bcf86cd799439011",
      "brd_title": "BRD HRM Employee Registration",
      "project_code": "PROJ-001",
      "total_clauses": 5,
      "status_counts": {...},
      "created_at": "2026-08-03T10:30:00"
    }
  ]
}
```

## 4. Get BRD Clauses (with optional status filter)

**Endpoint:** `GET /api/normalize/get-brd-clauses/{brd_id}?status={status}`

**Example - All clauses:**
```
GET http://localhost:8001/api/normalize/get-brd-clauses/507f1f77bcf86cd799439011
```

**Example - Filter by status:**
```
GET http://localhost:8001/api/normalize/get-brd-clauses/507f1f77bcf86cd799439011?status=In Review
```

**Response:**
```json
{
  "brd_id": "507f1f77bcf86cd799439011",
  "brd_title": "BRD HRM Employee Registration",
  "total_clauses": 2,
  "status_filter": "In Review",
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "In Review",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    }
  ]
}
```

**Valid Status Values:**
- `Unprocessed`
- `In Review`
- `Normalised`
- `Needs Clarification`

## 5. Update Clause Status

**Endpoint:** `PUT /api/normalize/update-clause-status/{brd_id}/{source_ref}`

**Example:**
```
PUT http://localhost:8001/api/normalize/update-clause-status/507f1f77bcf86cd799439011/BRD-S3.2.1
```

**Request Body:**
```json
{
  "status": "Normalised"
}
```

**Response:**
```json
{
  "message": "Clause status updated successfully",
  "brd_id": "507f1f77bcf86cd799439011",
  "source_ref": "BRD-S3.2.1",
  "old_status": "In Review",
  "new_status": "Normalised",
  "status_counts": {
    "All": 5,
    "Unprocessed": 1,
    "In Review": 1,
    "Normalised": 3,
    "Needs Clarification": 0
  }
}
```

## 6. Search Clauses by Keyword

**Endpoint:** `GET /api/normalize/search-clauses/{brd_id}?keyword={keyword}`

**Example:**
```
GET http://localhost:8001/api/normalize/search-clauses/507f1f77bcf86cd799439011?keyword=task
```

**Response:**
```json
{
  "brd_id": "507f1f77bcf86cd799439011",
  "brd_title": "BRD HRM Employee Registration",
  "keyword": "task",
  "total_matches": 3,
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "Normalised",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    }
  ]
}
```

---

## 🆕 Get Clause by BRD ID and Source Ref

**Endpoint:** `GET /api/normalize/get-clause/{brd_id}/{source_ref}`

Get a specific clause by BRD ID and source reference.

**Example:**
```
GET http://localhost:8001/api/normalize/get-clause/6a70c844f7bc4b4a7c24c166/BRD-005
```

**Response:**
```json
{
  "brd_id": "6a70c844f7bc4b4a7c24c166",
  "brd_title": "BRD HRM Employee Registration",
  "project_id": 1,
  "project_code": "GSolve",
  "project_name": "GREEN GSolve",
  "clause": {
    "source_ref": "BRD-005",
    "clause_statement": "The system shall allow task creation with owner, priority and due date.",
    "page": 12,
    "type_suggestion": "Functional",
    "status": "In Review",
    "section": "3.2 Task Management",
    "extracted_keywords": ["task creation", "owner", "priority", "due date"]
  }
}
```

**cURL Example:**
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/api/normalize/get-clause/6a70c844f7bc4b4a7c24c166/BRD-005' \
  -H 'accept: application/json'
```

---

## 🆕 Get Clause by Source Ref Only (Search All BRDs)

**Endpoint:** `GET /api/normalize/get-clause-by-source-ref/{source_ref}`

Get a specific clause by source reference across ALL BRDs. Useful when you only know the source_ref but not the BRD ID.

**Example:**
```
GET http://localhost:8001/api/normalize/get-clause-by-source-ref/BRD-005
```

**Response:**
```json
{
  "source_ref": "BRD-005",
  "total_found": 2,
  "results": [
    {
      "brd_id": "6a70c844f7bc4b4a7c24c166",
      "brd_title": "BRD HRM Employee Registration",
      "project_id": 1,
      "project_code": "GSolve",
      "project_name": "GREEN GSolve",
      "clause": {
        "source_ref": "BRD-005",
        "clause_statement": "The system shall allow task creation with owner, priority and due date.",
        "page": 12,
        "type_suggestion": "Functional",
        "status": "In Review",
        "section": "3.2 Task Management",
        "extracted_keywords": ["task creation", "owner", "priority", "due date"]
      }
    },
    {
      "brd_id": "6a70c844f7bc4b4a7c24c167",
      "brd_title": "BRD Task Management System",
      "project_id": 1,
      "project_code": "GSolve",
      "project_name": "GREEN GSolve",
      "clause": {
        "source_ref": "BRD-005",
        "clause_statement": "Users must be able to assign tasks to team members.",
        "page": 8,
        "type_suggestion": "Functional",
        "status": "Normalised",
        "section": "2.1 User Management",
        "extracted_keywords": ["assign", "tasks", "team members"]
      }
    }
  ]
}
```

**cURL Example:**
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/api/normalize/get-clause-by-source-ref/BRD-005' \
  -H 'accept: application/json'
```

---

## 6. Search Clauses by Keyword (Original)

**Endpoint:** `GET /api/normalize/search-clauses/{brd_id}?keyword={keyword}`

**Example:**
```
GET http://localhost:8001/api/normalize/search-clauses/507f1f77bcf86cd799439011?keyword=task
```

**Response:**
```json
{
  "brd_id": "507f1f77bcf86cd799439011",
  "brd_title": "BRD HRM Employee Registration",
  "keyword": "task",
  "total_matches": 3,
  "clauses": [
    {
      "source_ref": "BRD-S3.2.1",
      "clause_statement": "The system shall allow task creation with owner, priority and due date.",
      "page": 12,
      "type_suggestion": "Functional",
      "status": "Normalised",
      "section": "3.2 Task Management",
      "extracted_keywords": ["task creation", "owner", "priority", "due date"]
    }
  ]
}
```

## 7. Delete BRD

**Endpoint:** `DELETE /api/normalize/delete-brd/{brd_id}`

**Example:**
```
DELETE http://localhost:8001/api/normalize/delete-brd/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "message": "BRD deleted successfully",
  "brd_id": "507f1f77bcf86cd799439011"
}
```

---

## cURL Examples

### Add BRD Data
```bash
curl -X POST "http://localhost:8001/api/normalize/add-brd" \
  -H "Content-Type: application/json" \
  -d '{
    "brd_title": "BRD HRM Employee Registration",
    "project_code": "PROJ-001",
    "project_name": "HR Management System",
    "clauses": [
      {
        "source_ref": "BRD-S3.2.1",
        "clause_statement": "The system shall allow task creation with owner, priority and due date.",
        "page": 12,
        "type_suggestion": "Functional",
        "status": "In Review",
        "section": "3.2 Task Management",
        "extracted_keywords": ["task creation", "owner", "priority", "due date"]
      }
    ]
  }'
```

### Get BRD Data
```bash
curl -X GET "http://localhost:8001/api/normalize/get-brd/507f1f77bcf86cd799439011"
```

### Update Clause Status
```bash
curl -X PUT "http://localhost:8001/api/normalize/update-clause-status/507f1f77bcf86cd799439011/BRD-S3.2.1" \
  -H "Content-Type: application/json" \
  -d '{"status": "Normalised"}'
```

### Search Clauses
```bash
curl -X GET "http://localhost:8001/api/normalize/search-clauses/507f1f77bcf86cd799439011?keyword=task"
```

---

## Python Example

```python
import requests

BASE_URL = "http://localhost:8001/api/normalize"

# 🆕 Add BRD by GSolve Project ID (Recommended)
brd_data = {
    "brd_title": "BRD HRM Employee Registration",
    "project_id": 1,  # GSolve project ID
    "clauses": [
        {
            "source_ref": "BRD-S3.2.1",
            "clause_statement": "The system shall allow task creation with owner, priority and due date.",
            "page": 12,
            "type_suggestion": "Functional",
            "status": "In Review",
            "section": "3.2 Task Management",
            "extracted_keywords": ["task creation", "owner", "priority", "due date"]
        }
    ]
}

response = requests.post(f"{BASE_URL}/add-brd-by-project", json=brd_data)
result = response.json()
print(result)

# Get BRD ID and Project ID from response
brd_id = result["brd_id"]
project_id = result["project_details"]["gsolve_project_id"]

# Get all BRDs for this project
response = requests.get(f"{BASE_URL}/get-brds-by-project/{project_id}")
print(response.json())

# ---- OR use the original method ----

# Add BRD Data (Original method - manual project details)
brd_data = {
    "brd_title": "BRD HRM Employee Registration",
    "project_code": "PROJ-001",
    "project_name": "HR Management System",
    "clauses": [
        {
            "source_ref": "BRD-S3.2.1",
            "clause_statement": "The system shall allow task creation with owner, priority and due date.",
            "page": 12,
            "type_suggestion": "Functional",
            "status": "In Review",
            "section": "3.2 Task Management",
            "extracted_keywords": ["task creation", "owner", "priority", "due date"]
        }
    ]
}

response = requests.post(f"{BASE_URL}/add-brd", json=brd_data)
print(response.json())

# Get BRD ID from response
brd_id = response.json()["brd_id"]

# Get BRD Data
response = requests.get(f"{BASE_URL}/get-brd/{brd_id}")
print(response.json())

# Update Clause Status
response = requests.put(
    f"{BASE_URL}/update-clause-status/{brd_id}/BRD-S3.2.1",
    json={"status": "Normalised"}
)
print(response.json())

# Search Clauses
response = requests.get(f"{BASE_URL}/search-clauses/{brd_id}?keyword=task")
print(response.json())
```

---

## API Interactive Documentation

Once the server is running, you can access:

- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc

These provide interactive documentation where you can test all endpoints directly from the browser.

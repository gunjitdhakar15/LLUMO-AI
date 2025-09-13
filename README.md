# Employee Management API LLUMO AI

Python + MongoDB assessment solution (FastAPI).

---

## Setup

### Prerequisites
- Python 3.10+
- MongoDB running locally (`mongodb://localhost:27017`)

### Install Dependencies

```pip install -r requirements.txt```


## Endpoints
### CRUD

* POST /employees → Create new employee (unique employee_id)

* GET /employees/{employee_id} → Get by ID (404 if not found)

* PUT /employees/{employee_id} → Partial update

* DELETE /employees/{employee_id} → Delete employee

* Query & Aggregation

* GET /employees?department=Engineering → List by department, sorted by joining_date

* GET /employees/avg-salary → Average salary per department

* GET /employees/search?skill=Python → Search by skill

## Run Server
```uvicorn main:app --reload --host 0.0.0.0 --port 8000```


Open http://localhost:8000/docs
 for Swagger UI.

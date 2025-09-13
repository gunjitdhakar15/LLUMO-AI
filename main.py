# main.py
from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import motor.motor_asyncio
import os
import jwt
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("DATABASE", "assessment_db")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# FastAPI app
app = FastAPI(title="Employee Assessment API")

# MongoDB client & collection
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE]
collection = db["employees"]

# JWT security
bearer = HTTPBearer()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> Dict[str, Any]:
    if not JWT_SECRET:  # auth disabled
        return {"sub": "anonymous"}
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


# --------------------- MODELS ---------------------
class EmployeeBase(BaseModel):
    name: Optional[str]
    department: Optional[str]
    salary: Optional[float]
    joining_date: Optional[datetime]
    skills: Optional[List[str]]


class EmployeeCreate(EmployeeBase):
    employee_id: str = Field(..., min_length=1)
    name: str
    department: str
    salary: float
    joining_date: datetime
    skills: List[str]


class EmployeeUpdate(EmployeeBase):
    pass  # all fields optional for partial update


class EmployeeOut(EmployeeCreate):
    pass


# --------------------- HELPERS ---------------------
def doc_to_employee(doc: Dict) -> Dict:
    return {
        "employee_id": doc.get("employee_id"),
        "name": doc.get("name"),
        "department": doc.get("department"),
        "salary": doc.get("salary"),
        "joining_date": doc.get("joining_date"),
        "skills": doc.get("skills", []),
    }


@app.on_event("startup")
async def startup():
    # Ensure unique index on employee_id
    await collection.create_index("employee_id", unique=True)


# --------------------- CRUD ENDPOINTS ---------------------
@app.post(
    "/employees",
    response_model=EmployeeOut,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
async def create_employee(emp: EmployeeCreate):
    doc = emp.dict()
    try:
        await collection.insert_one(doc)
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=400, detail="employee_id must be unique")
        raise
    return doc_to_employee(doc)


@app.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: str):
    doc = await collection.find_one({"employee_id": employee_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Employee not found")
    return doc_to_employee(doc)


@app.put(
    "/employees/{employee_id}",
    response_model=EmployeeOut,
    dependencies=[Depends(get_current_user)],
)
async def update_employee(employee_id: str, update: EmployeeUpdate):
    update_data = {k: v for k, v in update.dict(exclude_unset=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    result = await collection.update_one(
        {"employee_id": employee_id}, {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")

    doc = await collection.find_one({"employee_id": employee_id})
    return doc_to_employee(doc)


@app.delete("/employees/{employee_id}", dependencies=[Depends(get_current_user)])
async def delete_employee(employee_id: str):
    result = await collection.delete_one({"employee_id": employee_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"status": "success", "message": f"Employee {employee_id} deleted"}


# --------------------- QUERY & AGGREGATION ---------------------
@app.get("/employees", response_model=List[EmployeeOut])
async def list_employees(
    department: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = {}
    if department:
        query["department"] = department
    skip = (page - 1) * limit
    cursor = collection.find(query).sort("joining_date", -1).skip(skip).limit(limit)
    results = [doc_to_employee(doc) async for doc in cursor]
    return results


@app.get("/employees/avg-salary")
async def avg_salary():
    pipeline = [
        {"$group": {"_id": "$department", "avg_salary": {"$avg": "$salary"}}},
        {
            "$project": {
                "_id": 0,
                "department": "$_id",
                "avg_salary": {"$round": ["$avg_salary", 2]},
            }
        },
    ]
    cursor = collection.aggregate(pipeline)
    return [doc async for doc in cursor]


@app.get("/employees/search", response_model=List[EmployeeOut])
async def search_by_skill(skill: str = Query(...)):
    cursor = collection.find({"skills": {"$in": [skill]}})
    return [doc_to_employee(doc) async for doc in cursor]


# --------------------- AUTH HELPERS ---------------------
@app.post("/token")
async def get_token(sub: str = "test-user"):
    if not JWT_SECRET:
        return {"token": "auth_disabled"}
    payload = {"sub": sub, "exp": datetime.utcnow() + timedelta(hours=2)}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token}

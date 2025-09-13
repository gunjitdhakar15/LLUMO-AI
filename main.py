import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import date
from dotenv import load_dotenv

# Load env vars
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("DATABASE", "assessment_db")

# Init FastAPI
app = FastAPI(title="Employee Management API")

# MongoDB connection
client = AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE]
collection = db["employees"]

# ---------- MODELS ----------
class Employee(BaseModel):
    employee_id: str = Field(..., example="E123")
    name: str
    department: str
    salary: float
    joining_date: date
    skills: List[str]

class UpdateEmployee(BaseModel):
    name: Optional[str]
    department: Optional[str]
    salary: Optional[float]
    joining_date: Optional[date]
    skills: Optional[List[str]]

# ---------- QUERYING ----------
@app.get("/employees/avg-salary")
async def avg_salary():
    pipeline = [
        {"$group": {"_id": "$department", "avg_salary": {"$avg": "$salary"}}},
        {"$project": {"department": "$_id", "avg_salary": 1, "_id": 0}}
    ]
    result = await collection.aggregate(pipeline).to_list(length=None)
    return result if result else []

@app.get("/employees/search")
async def search_employees(skill: str):
    cursor = collection.find({"skills": skill}, {"_id": 0})
    employees = await cursor.to_list(length=None)
    return employees

@app.get("/employees")
async def list_employees(
    department: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=50)
):
    query = {}
    if department:
        query["department"] = department
    cursor = (
        collection.find(query, {"_id": 0})
        .sort("joining_date", -1)
        .skip(skip)
        .limit(limit)
    )
    employees = await cursor.to_list(length=limit)
    return employees

# ---------- CRUD ----------
@app.post("/employees")
async def create_employee(employee: Employee):
    existing = await collection.find_one({"employee_id": employee.employee_id})
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    await collection.insert_one(employee.dict())
    return {"message": "Employee created successfully"}

@app.put("/employees/{employee_id}")
async def update_employee(employee_id: str, updates: UpdateEmployee):
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await collection.update_one({"employee_id": employee_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee updated successfully"}

@app.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str):
    result = await collection.delete_one({"employee_id": employee_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee deleted successfully"}

@app.get("/employees/{employee_id}")
async def get_employee(employee_id: str):
    employee = await collection.find_one({"employee_id": employee_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

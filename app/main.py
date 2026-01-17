from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, database
from .models import OTPCode
from .email_utils import send_otp_email

from datetime import datetime, timedelta
import random

# ---------------- APP SETUP ---------------- #

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

templates = Jinja2Templates(directory="frontend")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ---------------- OTP HELPERS ---------------- #

def generate_otp():
    return str(random.randint(100000, 999999))


def save_otp(email: str):
    db = database.SessionLocal()

    # delete any previous OTP for this email
    db.query(OTPCode).filter(OTPCode.email == email).delete()

    otp = generate_otp()
    record = OTPCode(
        email=email,
        otp=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )

    db.add(record)
    db.commit()
    db.close()

    # SEND OTP TO GMAIL
    send_otp_email(email, otp)

# ---------------- AUTH ROUTES ---------------- #

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "error": error}
    )


@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or user.password_hash != password:
        return RedirectResponse("/?error=Invalid Credentials", status_code=303)

    save_otp(email)

    response = RedirectResponse("/otp", status_code=303)
    response.set_cookie("otp_email", email)
    return response


@app.post("/register")
async def register(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    if db.query(models.User).filter(models.User.email == email).first():
        return RedirectResponse("/?error=Email already registered", status_code=303)

    user = models.User(email=email, password_hash=password)
    db.add(user)
    db.commit()

    save_otp(email)

    response = RedirectResponse("/otp", status_code=303)
    response.set_cookie("otp_email", email)
    return response


@app.get("/otp", response_class=HTMLResponse)
def otp_page(request: Request):
    return templates.TemplateResponse("otp.html", {"request": request})


@app.post("/verify-otp")
async def verify_otp(
    request: Request,
    otp0: str = Form(...),
    otp1: str = Form(...),
    otp2: str = Form(...),
    otp3: str = Form(...),
    otp4: str = Form(...),
    otp5: str = Form(...)
):
    entered_otp = otp0 + otp1 + otp2 + otp3 + otp4 + otp5
    email = request.cookies.get("otp_email")

    if not email:
        return RedirectResponse("/", status_code=303)

    db = database.SessionLocal()
    record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.otp == entered_otp
    ).first()

    if not record or record.expires_at < datetime.utcnow():
        return templates.TemplateResponse(
            "otp.html",
            {"request": request, "error": "Invalid or expired OTP"}
        )

    db.delete(record)
    db.commit()
    db.close()

    response = RedirectResponse("/dashboard", status_code=303)
    response.delete_cookie("otp_email")
    response.set_cookie("user_email", email)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("user_email")
    return response

# ---------------- DASHBOARD ---------------- #

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(database.get_db)):
    user_email = request.cookies.get("user_email")
    if not user_email:
        return RedirectResponse("/")

    user = db.query(models.User).filter(models.User.email == user_email).first()
    if not user:
        return RedirectResponse("/")

    tasks = db.query(models.Task).filter(
        models.Task.owner_id == user.id
    ).order_by(models.Task.due_date.asc()).all()

    stats = {
        "total": len(tasks),
        "pending": len([t for t in tasks if t.status == "Pending"]),
        "completed": len([t for t in tasks if t.status == "Completed"]),
        "completion_rate": int(
            (len([t for t in tasks if t.status == "Completed"]) / len(tasks)) * 100
        ) if tasks else 0
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "tasks": tasks, "stats": stats}
    )

# ---------------- TASK ACTIONS ---------------- #

@app.post("/tasks/add")
async def add_task(
    request: Request,
    title: str = Form(...),
    due_date: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user_email = request.cookies.get("user_email")
    if not user_email:
        return RedirectResponse("/")

    user = db.query(models.User).filter(models.User.email == user_email).first()
    if not user:
        return RedirectResponse("/")

    try:
        dt = datetime.strptime(due_date, "%Y-%m-%d")
    except:
        dt = datetime.utcnow()

    task = models.Task(title=title, due_date=dt, owner_id=user.id)
    db.add(task)
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/tasks/complete/{task_id}")
async def complete_task(task_id: int, db: Session = Depends(database.get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.status = "Completed"
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/tasks/delete/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(database.get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)

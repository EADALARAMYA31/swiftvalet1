from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import SessionLocal
from api.models import (
    ValetDriver,
    ParkingSession,
    SessionEvent
)
import random
router = APIRouter(prefix="/driver", tags=["Driver"])


# =========================
# DB SESSION
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def log_event(db, session_id, event):
    db.add(
        SessionEvent(
            session_id=session_id,
            event=event
        )
    )
    db.commit()

# =========================
# LOGIN
# =========================
@router.post("/login")
def driver_login(data: dict, db: Session = Depends(get_db)):

    driver_name = data.get("driver_id")
    pin = data.get("pin")
    print("LOGIN NAME:", driver_name)
    print("LOGIN PIN:", pin)
    driver = db.query(ValetDriver).filter(
        ValetDriver.name == driver_name,
        ValetDriver.pin == pin
    ).first()

    if not driver:
        raise HTTPException(
            status_code=401,
            detail="Driver not found"
        )

    if str(driver.pin) != str(pin):
        raise HTTPException(
            status_code=401,
            detail="Invalid PIN"
        )

    return {
        "success": True,
        "driver": {
            "id": driver.id,
            "name": driver.name,
            "phone": driver.phone
        }
    }


# =========================
# VEHICLE IMAGE UPLOAD (OCR PLACEHOLDER)
# =========================
@router.post("/upload")
def upload_vehicle_image(data: dict):

    image_data = data.get("image")

    if not image_data:
        return {"success": False}

    detected_plate = "TS09AB1234"

    return {
        "success": True,
        "plate": detected_plate
    }


# =========================
# ASSIGN DRIVER
# =========================
@router.post("/assign")
def assign_driver(data: dict, db: Session = Depends(get_db)):

    session_id = data.get("session_id")
    driver_id = data.get("driver_id")

    session = db.query(ParkingSession).filter(
        ParkingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 🚨 PREVENT DUPLICATE ASSIGNMENT
    existing = db.query(ParkingSession).filter(
        ParkingSession.vehicle_id == session.vehicle_id,
        ParkingSession.state.in_(["PARKED", "IN_RETRIEVAL", "PICKED"])
    ).first()

    if existing:
        return {
            "message": "active session already exists",
            "id": existing.id,
            "state": existing.state
        }

    session.driver_id = driver_id
    session.state = "IN_RETRIEVAL"

    db.commit()

    return {"success": True, "message": "Driver assigned"}


# =========================
# DRIVER JOBS
# =========================
@router.get("/jobs/{driver_id}")
def driver_jobs(driver_id: int, db: Session = Depends(get_db)):

    sessions = db.query(ParkingSession).filter(
    ParkingSession.driver_id == driver_id,
    ParkingSession.state != "PAID_AND_EXITED"
).order_by(ParkingSession.id.desc()).all()

    return [
        {
            "id": s.id,
            "plate": s.vehicle.plate_number,
            "customer": (
                s.vehicle.customer.name
                if s.vehicle and s.vehicle.customer
            else ""
            ),
            "phone": (
                s.vehicle.customer.phone
                if s.vehicle and s.vehicle.customer
                else ""
            ),
            "zone": s.park_zone,
            "otp": s.otp,
        "state": s.state
        }
        for s in sessions
    ]

# =========================
# MARK: PICKED (GOING TO FETCH CAR)
# =========================
@router.post("/session/{session_id}/picked")
def picked_vehicle(session_id: int, db: Session = Depends(get_db)):

    session = db.query(ParkingSession).filter(
        ParkingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 🔥 FIX: correct state
    if session.state != "REQUESTED":
        return {
            "success": False,
            "message": "Vehicle is not ready for pickup."
        }

    session.state = "IN_RETRIEVAL"
    db.commit()

    log_event(
        db,
        session.id,
        "Driver picked vehicle"
    )

    return {"success": True, "state": session.state}


# =========================
# MARK: DELIVERED (CAR HANDED OVER)
# =========================
@router.post("/session/{session_id}/delivered")
def delivered_vehicle(session_id: int, db: Session = Depends(get_db)):

    session = db.query(ParkingSession).filter(
        ParkingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.state != "IN_RETRIEVAL":
        return {
            "success": False,
            "message": "Vehicle is not being retrieved."
        }

    session.state = "PAYMENT_PENDING"
    db.commit()

    log_event(
        db,
        session.id,
        "Vehicle delivered"
    )

    return {"success": True, "state": session.state}


# =========================
# ANALYTICS
# =========================
@router.get("/analytics/{driver_id}")
def driver_analytics(driver_id: int, db: Session = Depends(get_db)):

    active = db.query(ParkingSession).filter(
        ParkingSession.driver_id == driver_id,
        ParkingSession.state.in_(["PARKED", "IN_RETRIEVAL"])
    ).count()

    completed = db.query(ParkingSession).filter(
        ParkingSession.driver_id == driver_id,
        ParkingSession.state == "PAID_AND_EXITED"
    ).count()

    return {
        "driver": driver_id,
        "active": active,
        "completed": completed
    }


# =========================
# DEBUG: VIEW SESSIONS
# =========================
@router.get("/debug/sessions")
def debug_sessions(db: Session = Depends(get_db)):

    sessions = db.query(ParkingSession).all()

    return [
        {
            "id": s.id,
            "state": s.state,
            "driver_id": s.driver_id,
            "plate": s.vehicle.plate_number if s.vehicle else None
        }
        for s in sessions
    ]


# =========================
# DEBUG: CREATE TEST SESSION
# =========================
@router.get("/debug/create-session")
def create_session(db: Session = Depends(get_db)):

    new_session = ParkingSession(
        vehicle_id=1,
        driver_id=1,
        state="PARKED",
        park_zone="A1"
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {
        "message": "created",
        "id": new_session.id,
        "state": new_session.state,
        "driver_id": new_session.driver_id,
        "plate": new_session.vehicle.plate_number
    }
@router.get("/debug/clear-sessions")
def clear_sessions(db: Session = Depends(get_db)):

    db.query(ParkingSession).delete()
    db.commit()

    return {"message": "all sessions deleted"}
@router.get("/debug/db-check")
def db_check(db: Session = Depends(get_db)):
    sessions = db.query(ParkingSession).all()

    return {
        "count": len(sessions),
        "rows": [
            {
                "id": s.id,
                "driver_id": s.driver_id,
                "state": s.state
            }
            for s in sessions
        ]
    }
@router.post("/whatsapp-web")
def whatsapp_web(payload: dict, db: Session = Depends(get_db)):

    phone = payload.get("from")
    text = (payload.get("body") or "").lower()

    # =========================
    # STEP 1: GET MY CAR FLOW
    # =========================
    if "get my car" in text or "reset" in text:

        session = db.query(ParkingSession).filter(
            ParkingSession.state == "PARKED"
        ).first()

        if not session:
            return {"reply": "❌ No parked car found"}

        otp = str(random.randint(100000, 999999))
        session.otp = otp
        db.commit()

        return {
            "reply": f"🚗 Your OTP is {otp}. Reply with it to confirm."
        }

    # =========================
    # STEP 2: OTP VALIDATION
    # =========================
    if text.isdigit() and len(text) == 6:

        session = db.query(ParkingSession).filter(
            ParkingSession.otp == text
        ).first()

        if not session:
            return {"reply": "❌ Invalid OTP"}

        session.state = "IN_RETRIEVAL"
        db.commit()

        return {
            "reply": "✅ Verified! Driver is coming to bring your car."
        }

    # ========================= 
    # DEFAULT RESPONSE
    # =========================
    return {
        "reply": "👋 Send 'get my car' when you want your vehicle."
    }
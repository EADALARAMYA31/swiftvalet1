from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.db import SessionLocal
from api.models import Customer, Vehicle, ValetDriver, ParkingSession

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    vehicles = db.query(Vehicle).all()
    drivers = db.query(ValetDriver).all()
    sessions = db.query(ParkingSession).all()

    html = """
    <html>
    <head>
        <title>SwiftValet Operator Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: Arial; background:#f4f6f8; padding:20px; }
            h1 { color:#1f2937; }
            h2 { color:#2563eb; margin-top:30px; }
            table { width:100%; border-collapse:collapse; background:white; margin-top:10px; }
            th, td { padding:10px; border:1px solid #ddd; text-align:left; }
            th { background:#111827; color:white; }
            .PARKED { color:green; font-weight:bold; }
            .OTP_PENDING { color:#ca8a04; font-weight:bold; }
            .REQUESTED { color:orange; font-weight:bold; }
            .IN_RETRIEVAL { color:blue; font-weight:bold; }
            .PAYMENT_PENDING { color:purple; font-weight:bold; }
            .PAID_AND_EXITED { color:gray; font-weight:bold; }
        </style>
    </head>
    <body>
        <h1>🚗 SwiftValet Operator Dashboard</h1>
        <p>Auto refreshes every 5 seconds</p>
    """

    html += "<h2>Customers</h2><table><tr><th>ID</th><th>Name</th><th>Phone</th></tr>"
    for c in customers:
        html += f"<tr><td>{c.id}</td><td>{c.name}</td><td>{c.phone}</td></tr>"
    html += "</table>"

    html += "<h2>Vehicles</h2><table><tr><th>ID</th><th>Plate</th><th>Customer ID</th></tr>"
    for v in vehicles:
        html += f"<tr><td>{v.id}</td><td>{v.plate_number}</td><td>{v.customer_id}</td></tr>"
    html += "</table>"

    html += "<h2>Drivers</h2><table><tr><th>ID</th><th>Name</th><th>Phone</th></tr>"
    for d in drivers:
        html += f"<tr><td>{d.id}</td><td>{d.name}</td><td>{d.phone}</td></tr>"
    html += "</table>"

    html += """
    <h2>Parking Sessions</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Vehicle ID</th>
            <th>Driver ID</th>
            <th>State</th>
            <th>OTP</th>
            <th>Park Zone</th>
        </tr>
    """

    for s in sessions:
        html += f"""
        <tr>
            <td>{s.id}</td>
            <td>{s.vehicle_id}</td>
            <td>{s.driver_id}</td>
            <td class="{s.state}">{s.state}</td>
            <td>{s.otp}</td>
            <td>{s.park_zone}</td>
        </tr>
        """

    html += "</table>"
    html += "</body></html>"

    return html
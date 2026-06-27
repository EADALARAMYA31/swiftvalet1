from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.db import SessionLocal
from api.models import (
    Customer,
    Vehicle,
    ValetDriver,
    ParkingSession
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/sessions/live")
def get_live_sessions(db: Session = Depends(get_db)):

    sessions = db.query(ParkingSession).all()

    data = []

    for session in sessions:

        events = [
            {
                "event": e.event,
                "time": e.created_at.strftime("%H:%M:%S")
            }
            for e in session.events
        ]

        data.append({
            "id": session.id,
            "plate": session.vehicle.plate_number,
            "customer": session.vehicle.customer.name,
            "state": session.state,
            "zone": session.park_zone,
            "driver": session.driver.name if session.driver else "Unassigned",
            "events": events
        })

    return data
@router.get("/sessions/live-json")
def live_sessions(db: Session = Depends(get_db)):

    sessions = db.query(ParkingSession).order_by(ParkingSession.id.desc()).all()

    return [
        {
            "id": s.id,
            "plate": s.vehicle.plate_number if s.vehicle else "",
            "customer": s.vehicle.customer.name if s.vehicle and s.vehicle.customer else "",
            "state": s.state,
            "zone": s.park_zone,
            "driver": s.driver.name if s.driver else "Unassigned"
        }
        for s in sessions
    ]
@router.get("/", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):

    customers = db.query(Customer).all()

    vehicles = db.query(Vehicle).all()

    drivers = db.query(ValetDriver).all()

    sessions = (
        db.query(ParkingSession)
        .order_by(ParkingSession.id.desc())
        .all()
    )

    total_parked = db.query(ParkingSession).filter(
        ParkingSession.state == "PARKED"
    ).count()

    total_requested = db.query(ParkingSession).filter(
        ParkingSession.state == "REQUESTED"
    ).count()

    total_retrieval = db.query(ParkingSession).filter(
        ParkingSession.state == "IN_RETRIEVAL"
    ).count()

    total_payment_pending = db.query(ParkingSession).filter(
        ParkingSession.state == "PAYMENT_PENDING"
    ).count()

    total_completed = db.query(ParkingSession).filter(
        ParkingSession.state == "PAID_AND_EXITED"
    ).count()

    html = f"""

    <!DOCTYPE html>

    <html>

    <head>

        <title>SwiftValet AI Dashboard</title>

        <meta http-equiv="refresh" content="5">

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                background: #0f172a;
                color: white;
                font-family: 'Segoe UI';
                padding: 25px;
            }}

            .topbar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 35px;
            }}

            .topbar h1 {{
                font-size: 38px;
                font-weight: bold;
            }}

            .topbar p {{
                color: #94a3b8;
                margin-top: 8px;
            }}

            .live {{
                background: #22c55e;
                padding: 10px 18px;
                border-radius: 30px;
                font-weight: bold;
            }}

            .search-box {{
                margin-top: 20px;
                margin-bottom: 30px;
            }}

            .search-box input {{
                width: 100%;
                padding: 14px;
                border-radius: 12px;
                border: none;
                outline: none;
                background: #1e293b;
                color: white;
                font-size: 15px;
            }}

            .cards {{
                display: grid;
                grid-template-columns:
                repeat(auto-fit,minmax(220px,1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}

            .card {{
                background: linear-gradient(
                    145deg,
                    #1e293b,
                    #111827
                );

                padding: 25px;
                border-radius: 20px;
                box-shadow:
                0px 8px 20px rgba(0,0,0,0.3);

                transition: 0.3s;
            }}

            .card:hover {{
                transform: translateY(-5px);
            }}

            .card h3 {{
                color: #cbd5e1;
                margin-bottom: 15px;
            }}

            .card p {{
                font-size: 42px;
                font-weight: bold;
            }}

            .green {{ color: #22c55e; }}
            .orange {{ color: #f59e0b; }}
            .blue {{ color: #3b82f6; }}
            .purple {{ color: #a855f7; }}
            .gray {{ color: #94a3b8; }}

            .grid {{
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 25px;
                margin-bottom: 40px;
            }}

            .panel {{
                background: #111827;
                border-radius: 20px;
                padding: 25px;
                box-shadow:
                0px 8px 20px rgba(0,0,0,0.3);
            }}

            .panel h2 {{
                margin-bottom: 20px;
            }}

            .activity {{
                max-height: 500px;
                overflow-y: auto;
            }}

            .activity-item {{
                background: #1e293b;
                padding: 14px;
                border-radius: 12px;
                margin-bottom: 12px;
            }}

            .activity-item small {{
                color: #94a3b8;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                overflow: hidden;
                border-radius: 15px;
            }}

            th {{
                background: #1e293b;
                padding: 16px;
                text-align: left;
            }}

            td {{
                padding: 15px;
                border-top: 1px solid #1f2937;
            }}

            tr:hover {{
                background: #1e293b;
            }}

            .badge {{

                padding: 8px 16px;
                border-radius: 30px;
                font-size: 12px;
                font-weight: bold;
                display: inline-block;
            }}

            .PARKED {{
                background: rgba(34,197,94,0.2);
                color: #22c55e;
            }}

            .OTP_PENDING {{
                background: rgba(245,158,11,0.2);
                color: #f59e0b;
            }}

            .REQUESTED {{
                background: rgba(249,115,22,0.2);
                color: #f97316;
            }}

            .IN_RETRIEVAL {{
                background: rgba(59,130,246,0.2);
                color: #3b82f6;
            }}

            .PAYMENT_PENDING {{
                background: rgba(168,85,247,0.2);
                color: #a855f7;
            }}

            .PAID_AND_EXITED {{
                background: rgba(148,163,184,0.2);
                color: #94a3b8;
            }}

            .section {{
                margin-top: 40px;
            }}

            .footer {{
                margin-top: 40px;
                text-align: center;
                color: #64748b;
            }}

            .action-btn {{
                padding: 8px 14px;
                border: none;
                border-radius: 10px;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }}

            .picked-btn {{
                background: #2563eb;
            }}

            .deliver-btn {{
                background: #16a34a;
            }}

            .cancel-btn {{
                background: #dc2626;
            }}

        </style>

    </head>

    <body>

        <div class="topbar">

            <div>

                <h1>
                    🚗 SwiftValet AI Dashboard
                </h1>

                <p>
                    Real-time valet parking intelligence system
                </p>

            </div>

            <div class="live">
                ● LIVE
            </div>

        </div>

        <div class="search-box">

            <input
                type="text"
                id="searchInput"
                placeholder="Search vehicle, customer, driver..."
                onkeyup="searchTable()"
            >

        </div>

        <div class="cards">

            <div class="card">
                <h3>🟢 PARKED</h3>
                <p class="green">{total_parked}</p>
            </div>

            <div class="card">
                <h3>🟠 REQUESTED</h3>
                <p class="orange">{total_requested}</p>
            </div>

            <div class="card">
                <h3>🔵 IN RETRIEVAL</h3>
                <p class="blue">{total_retrieval}</p>
            </div>

            <div class="card">
                <h3>🟣 PAYMENT PENDING</h3>
                <p class="purple">{total_payment_pending}</p>
            </div>

            <div class="card">
                <h3>⚫ COMPLETED</h3>
                <p class="gray">{total_completed}</p>
            </div>

        </div>

        <div class="grid">

            <div class="panel">

                <h2>
                    📊 Live Operations Analytics
                </h2>

                <canvas id="myChart"></canvas>

            </div>

            <div class="panel">

                <h2>
                    ⚡ Live Activity Feed
                </h2>

                <div class="activity">

    """

    for s in sessions[:10]:

        vehicle_plate = (
            s.vehicle.plate_number
            if s.vehicle else "-"
        )

        html += f"""

        <div class="activity-item">

            <b>{vehicle_plate}</b><br>

            State changed to
            <b>{s.state}</b><br>

            <small>
                Session ID: {s.id}
            </small>

        </div>

        """

    html += """

                </div>

            </div>

        </div>

    """

    # PARKING SESSIONS

    html += """

    <div class="section">

    <h2>
        🚘 Live Parking Sessions
    </h2>

    <table id="sessionTable">

        <tr>
            <th>ID</th>
            <th>Vehicle</th>
            <th>Driver</th>
            <th>Status</th>
            <th>OTP</th>
            <th>Zone</th>
            <th>Actions</th>
        </tr>

    """

    for s in sessions:

        vehicle_plate = (
            s.vehicle.plate_number
            if s.vehicle else "-"
        )

        driver_name = (
            s.driver.name
            if s.driver else "-"
        )

        state_class = s.state

        html += f"""

        <tr>

            <td>
                #{s.id}
            </td>

            <td>

                <div style="
                    display:flex;
                    align-items:center;
                    gap:12px;
                ">

                    <img
                        src="https://cdn-icons-png.flaticon.com/512/744/744465.png"
                        width="55"

                        style="
                            border-radius:12px;
                            background:white;
                            padding:6px;
                        "
                    >

                    <div>

                        <div style="
                            font-weight:bold;
                            font-size:16px;
                        ">
                            {vehicle_plate}
                        </div>

                        <small style="
                            color:#94a3b8;
                        ">
                            SwiftValet Vehicle
                        </small>

                    </div>

                </div>

            </td>

            <td>

                <div style="
                    font-weight:bold;
                ">
                    {driver_name}
                </div>

            </td>

            <td>

                <span class="badge {state_class}">
                    {s.state}
                </span>

            </td>

            <td>

                <div style="
                    font-weight:bold;
                    letter-spacing:2px;
                ">
                    {s.otp}
                </div>

            </td>

            <td>

                <div style="
                    background:#1e293b;
                    padding:8px 14px;
                    border-radius:12px;
                    display:inline-block;
                ">
                    {s.park_zone}
                </div>

            </td>

            <td>

                <div style="
                    display:flex;
                    gap:8px;
                    flex-wrap:wrap;
                ">

                    <button
                        class="action-btn picked-btn"
                    >
                        PICKED
                    </button>

                    <button
                        class="action-btn deliver-btn"
                    >
                        DELIVERED
                    </button>

                    <button
                        class="action-btn cancel-btn"
                    >
                        CANCEL
                    </button>

                </div>

            </td>

        </tr>

        """

    html += """

    </table>

    </div>

    """

    # CUSTOMERS

    html += """

    <div class="section">

    <h2>
        👥 Customers
    </h2>

    <table>

        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Phone</th>
        </tr>

    """

    for c in customers:

        html += f"""

        <tr>
            <td>{c.id}</td>
            <td>{c.name}</td>
            <td>{c.phone}</td>
        </tr>

        """

    html += """

    </table>

    </div>

    """

    # VEHICLES

    html += """

    <div class="section">

    <h2>
        🚗 Vehicles
    </h2>

    <table>

        <tr>
            <th>ID</th>
            <th>Plate</th>
            <th>Customer ID</th>
        </tr>

    """

    for v in vehicles:

        html += f"""

        <tr>
            <td>{v.id}</td>
            <td>{v.plate_number}</td>
            <td>{v.customer_id}</td>
        </tr>

        """

    html += """

    </table>

    </div>

    """

    # DRIVERS

    html += """

    <div class="section">

    <h2>
        🧑‍✈️ Drivers
    </h2>

    <table>

        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Phone</th>
        </tr>

    """

    for d in drivers:

        html += f"""

        <tr>
            <td>{d.id}</td>
            <td>{d.name}</td>
            <td>{d.phone}</td>
        </tr>

        """

    html += """

    </table>

    </div>

    """

    html += f"""

    <div class="footer">

        SwiftValet AI • Smart Parking Management Platform

    </div>

    <script>

        const ctx =
        document.getElementById('myChart');

        new Chart(ctx, {{

            type: 'bar',

            data: {{

                labels: [
                    'Parked',
                    'Requested',
                    'Retrieval',
                    'Payment',
                    'Completed'
                ],

                datasets: [{{
                    label: 'Vehicle Analytics',

                    data: [
                        {total_parked},
                        {total_requested},
                        {total_retrieval},
                        {total_payment_pending},
                        {total_completed}
                    ],

                    borderWidth: 1
                }}]
            }},

            options: {{
                responsive: true
            }}
        }});

        function searchTable() {{

            let input =
            document.getElementById("searchInput");

            let filter =
            input.value.toUpperCase();

            let table =
            document.getElementById("sessionTable");

            let tr =
            table.getElementsByTagName("tr");

            for (let i = 1; i < tr.length; i++) {{

                let found = false;

                let td =
                tr[i].getElementsByTagName("td");

                for (let j = 0; j < td.length; j++) {{

                    if (
                        td[j].innerHTML
                        .toUpperCase()
                        .indexOf(filter) > -1
                    ) {{
                        found = true;
                    }}
                }}

                tr[i].style.display =
                found ? "" : "none";
            }}
        }}

    </script>

    </body>

    </html>

    """

    return html

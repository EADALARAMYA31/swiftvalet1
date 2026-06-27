import math
from api.models import ValetDriver

from api.services.notifications import notify_driver
# --- REAL DISTANCE (Haversine formula) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(lat1) * math.cos(lat2) *
        math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))

    return R * c  # distance in KM


# --- FIND BEST DRIVER ---
def find_nearest_driver(db, lat, lng):
    drivers = db.query(ValetDriver).filter(
        ValetDriver.status == "FREE"
    ).all()

    best_driver = None
    best_score = float("inf")

    for d in drivers:
        if d.lat is None or d.lng is None:
            continue

        distance = calculate_distance(lat, lng, d.lat, d.lng)

        # optional: workload penalty (IMPORTANT for scale)
        workload_penalty = getattr(d, "active_jobs", 0) * 0.5

        score = distance + workload_penalty

        if score < best_score:
            best_score = score
            best_driver = d

    return best_driver


# --- ASSIGN DRIVER TO SESSION ---
def assign_driver(db, session):
    driver = (
        db.query(ValetDriver)
        .filter(ValetDriver.status == "AVAILABLE")
        .order_by(ValetDriver.id)
        .first()
    )

    if not driver:
        print("❌ No AVAILABLE driver found")
        return None

    print(f"✅ Assigning Driver: {driver.id} - {driver.name}")

    session.driver_id = driver.id
    session.state = "REQUESTED"

    driver.status = "BUSY"
    driver.active_jobs = (driver.active_jobs or 0) + 1

    db.commit()
    db.refresh(driver)
    db.refresh(session)

    print(
        f"Session {session.id} -> Driver {session.driver_id}, "
        f"Status={driver.status}, ActiveJobs={driver.active_jobs}"
    )

    return driver
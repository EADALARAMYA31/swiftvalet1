def mark_picked(db, session_id, driver):
    session = db.query(ParkingSession).get(session_id)

    session.state = "IN_RETRIEVAL"

    log_event(db, session_id, "Driver picked vehicle")

    db.commit()
    return session
def mark_delivered(db, session_id, driver):
    session = db.query(ParkingSession).get(session_id)

    session.state = "PAYMENT_PENDING"

    driver.active_jobs -= 1

    if driver.active_jobs <= 0:
        driver.status = "FREE"
        driver.active_jobs = 0

    log_event(db, session_id, "Vehicle delivered")

    db.commit()
    return session
def mark_paid(db, session_id):
    session = db.query(ParkingSession).get(session_id)

    session.state = "PAID_AND_EXITED"

    log_event(db, session_id, "Payment completed")

    db.commit()
    return session
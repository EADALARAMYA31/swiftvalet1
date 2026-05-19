from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import random
import re

from api.db import SessionLocal
from api.models import Customer, Vehicle, ValetDriver, ParkingSession
from api.plate_extractor import extract_plate_from_image

router = APIRouter(prefix="/agent", tags=["SwiftValet Agent"])

agent_memory = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_otp():
    return str(random.randint(100000, 999999))


def wa_number(phone):
    phone = str(phone).replace("+", "").replace(" ", "")

    if "@lid" in phone or "@c.us" in phone:
        return phone

    if phone.startswith("91") and len(phone) == 12:
        return phone

    if len(phone) == 10:
        return "91" + phone

    return phone


def clean_db_phone(phone):
    phone = str(phone).replace("@c.us", "").replace("@lid", "")
    phone = phone.replace("+", "").replace(" ", "")

    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    return phone


def normalize_phone(phone):
    phone = str(phone)

    if "@lid" in phone:
        return phone

    phone = phone.replace("@c.us", "")
    phone = phone.replace("+", "")
    phone = phone.replace(" ", "")

    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    return phone


def reply_to_sender(message):
    return {"reply": message}


def reply_and_send(reply, send_to, message):
    return {
        "reply": reply,
        "sendTo": wa_number(send_to),
        "message": message
    }


def get_or_create_driver(db: Session, phone: str):
    driver = db.query(ValetDriver).filter(ValetDriver.phone == phone).first()

    if not driver:
        driver = ValetDriver(name="Valet Driver", phone=phone)
        db.add(driver)
        db.commit()
        db.refresh(driver)

    return driver


def create_or_update_session(db: Session, vehicle_id: int, driver_id: int, otp: str):
    session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_id == vehicle_id,
            ParkingSession.state.in_(
                ["PARKED", "OTP_PENDING", "REQUESTED", "IN_RETRIEVAL"]
            )
        )
        .first()
    )

    if not session:
        session = ParkingSession(
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            state="PARKED",
            otp=otp,
            park_zone="A1"
        )
        db.add(session)
    else:
        session.driver_id = driver_id
        session.state = "PARKED"
        session.otp = otp

    db.commit()
    db.refresh(session)
    return session


def extract_clean_plate(raw_text):
    raw_text = str(raw_text).upper()

    matches = re.findall(
        r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}",
        raw_text
    )

    if matches:
        return matches[0]

    cleaned = re.sub(r"[^A-Z0-9]", "", raw_text)
    return cleaned[:20] if cleaned else "PLATE_NOT_FOUND"


def continue_after_plate_confirmation(db, sender_phone, plate):
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()

    if not vehicle:
        agent_memory[sender_phone] = {
            "step": "waiting_customer_details",
            "plate": plate
        }

        return reply_to_sender(
            f"""Vehicle {plate} is not registered.

Please send customer details in this format:
Name, Phone"""
        )

    customer = vehicle.customer

    agent_memory[sender_phone] = {
        "step": "waiting_yes_no",
        "plate": plate,
        "vehicle_id": vehicle.id
    }

    return reply_to_sender(
        f"""Vehicle {plate} is already registered.

Customer Name: {customer.name}
Phone Number: {customer.phone}

Do you want to change the phone number?
Reply YES or NO."""
    )


@router.post("/whatsapp-web")
async def whatsapp_web_agent(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()

    print("DATA:", data)

    sender_phone = normalize_phone(data.get("from", ""))
    message = str(data.get("body", "")).strip()
    lower_msg = message.lower()

# EXISTING FLOW CONTINUES BELOW

    print("SENDER:", sender_phone)
    print("MESSAGE:", message)

    # RESET
    if lower_msg == "reset":
        if sender_phone in agent_memory:
            del agent_memory[sender_phone]

        return reply_to_sender(
            "Flow reset successfully. Please send car image."
        )

        # CUSTOMER SAYS GET MY CAR
        # CUSTOMER SAYS GET MY CAR
    if "get my car" in lower_msg:

        print("GET MY CAR HIT")

        session = (
            db.query(ParkingSession)
            .filter(ParkingSession.state == "PARKED")
            .order_by(ParkingSession.id.desc())
            .first()
        )

        print("SESSION:", session)

        if not session:
            return reply_to_sender("No active PARKED vehicle found.")

        vehicle = session.vehicle

        otp = generate_otp()
        session.otp = otp
        session.state = "OTP_PENDING"
        db.commit()

        return reply_to_sender(
            f"""Retrieval request received for vehicle {vehicle.plate_number}.

Your confirmation OTP is {otp}.
Reply with this OTP to confirm retrieval."""
        )

        # CUSTOMER OTP CONFIRMATION
        # CUSTOMER OTP CONFIRMATION
    if message.isdigit() and len(message) == 6:
        session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.otp == message,
                ParkingSession.state == "OTP_PENDING"
            )
            .order_by(ParkingSession.id.desc())
            .first()
        )

        if not session:
            return reply_to_sender("Invalid OTP or no OTP confirmation is pending.")

        session.state = "REQUESTED"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        customer_msg = f"""OTP verified successfully.

Your vehicle {vehicle.plate_number} retrieval request is confirmed.
State: REQUESTED"""

        driver_msg = f"""Customer {customer.name} requested vehicle {vehicle.plate_number}.

Customer Phone: {customer.phone}
Parking Zone: {session.park_zone}
State: REQUESTED

Reply PICKED when you start retrieval.
After pickup, reply DELIVERED after delivery."""

        return reply_and_send(
            customer_msg,
            session.driver.phone,
            driver_msg
        )

    # DRIVER SAYS PICKED
    if lower_msg == "picked":
        driver = (
            db.query(ValetDriver)
            .filter(ValetDriver.phone == sender_phone)
            .first()
        )

        if not driver:
            return reply_to_sender("Driver not found.")

        session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.driver_id == driver.id,
                ParkingSession.state == "REQUESTED"
            )
            .first()
        )

        if not session:
            return reply_to_sender("No REQUESTED vehicle assigned to you.")

        session.state = "IN_RETRIEVAL"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        driver_reply = f"""Vehicle {vehicle.plate_number} marked as IN_RETRIEVAL.

Please retrieve and deliver the vehicle.

After delivery, reply DELIVERED."""

        customer_msg = f"""Your vehicle {vehicle.plate_number} is on the way.

Driver has started retrieval.
State: IN_RETRIEVAL"""

        return reply_and_send(
            driver_reply,
            customer.phone,
            customer_msg
        )

    # DRIVER SAYS DELIVERED
    if lower_msg == "delivered":
        driver = (
            db.query(ValetDriver)
            .filter(ValetDriver.phone == sender_phone)
            .first()
        )

        if not driver:
            return reply_to_sender("Driver not found.")

        session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.driver_id == driver.id,
                ParkingSession.state == "IN_RETRIEVAL"
            )
            .first()
        )

        if not session:
            return reply_to_sender("No IN_RETRIEVAL vehicle assigned to you.")

        session.state = "PAYMENT_PENDING"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        driver_reply = f"""Vehicle {vehicle.plate_number} marked as DELIVERED.

State: PAYMENT_PENDING
Waiting for customer payment confirmation."""

        payment_msg = f"""Your vehicle {vehicle.plate_number} has been delivered successfully.

State: PAYMENT_PENDING

Please complete payment:
upi://pay?pa=swiftvalet@upi&pn=SwiftValet&am=100

Reply PAID after payment."""

        return reply_and_send(
            driver_reply,
            customer.phone,
            payment_msg
        )

        # CUSTOMER SAYS PAID
    if lower_msg == "paid":

        session = (
            db.query(ParkingSession)
            .filter(ParkingSession.state == "PAYMENT_PENDING")
            .order_by(ParkingSession.id.desc())
            .first()
        )

        if not session:
            return reply_to_sender(
                "No payment is pending for your vehicle."
            )

        session.state = "PAID_AND_EXITED"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        customer_msg = f"""Payment received successfully.

Vehicle {vehicle.plate_number} session completed.
State: PAID_AND_EXITED

Thank you for using SwiftValet."""

        driver_msg = f"""Payment received successfully for vehicle {vehicle.plate_number}.

Customer: {customer.name}
Customer Phone: {customer.phone}

State: PAID_AND_EXITED

Session completed successfully."""

        return reply_and_send(
            customer_msg,
            session.driver.phone,
            driver_msg
        )
        

    # MEMORY FLOWS
    if sender_phone in agent_memory:
        memory = agent_memory[sender_phone]
        step = memory["step"]

        # PLATE CONFIRMATION
        if step == "waiting_plate_confirmation":
            detected_plate = memory["plate"]

            if lower_msg == "yes":
                plate = detected_plate
            else:
                plate = extract_clean_plate(message)

            del agent_memory[sender_phone]

            return continue_after_plate_confirmation(db, sender_phone, plate)

        # NEW VEHICLE DETAILS
        if step == "waiting_customer_details":
            try:
                parts = message.split(",")

                if len(parts) != 2:
                    return reply_to_sender("Please send like: Name, Phone")

                name = parts[0].strip()
                customer_phone = parts[1].strip()
                customer_phone = customer_phone.replace(" ", "")
                customer_phone = customer_phone.replace("+91", "")

                if not customer_phone.isdigit() or len(customer_phone) != 10:
                    return reply_to_sender("Please send valid 10 digit phone number.")

                plate = memory["plate"]
                driver = get_or_create_driver(db, sender_phone)

                customer = (
                    db.query(Customer)
                    .filter(Customer.phone == customer_phone)
                    .first()
                )

                if not customer:
                    customer = Customer(
                        name=name,
                        phone=customer_phone
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)

                existing_vehicle = (
                    db.query(Vehicle)
                    .filter(Vehicle.plate_number == plate)
                    .first()
                )

                if existing_vehicle:
                    return reply_to_sender("This vehicle is already registered.")

                vehicle = Vehicle(
                    plate_number=plate,
                    customer_id=customer.id
                )
                db.add(vehicle)
                db.commit()
                db.refresh(vehicle)

                otp = generate_otp()

                create_or_update_session(
                    db=db,
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    otp=otp
                )

                del agent_memory[sender_phone]

                customer_msg = f"""Welcome to SwiftValet.

Your vehicle {plate} is parked.
Your OTP is {otp}.
State: PARKED

When you need the car, send:
get my car"""

                driver_msg = f"""Customer registered successfully.

Customer Name: {customer.name}
Vehicle {plate} linked with {customer_phone}.
State: PARKED"""

                return reply_and_send(
                    driver_msg,
                    customer_phone,
                    customer_msg
                )

            except Exception as e:
                print("WAITING_CUSTOMER_DETAILS ERROR:", e)
                db.rollback()
                return reply_to_sender(f"ERROR: {str(e)}")

        # EXISTING VEHICLE YES/NO
        if step == "waiting_yes_no":
            try:
                plate = memory["plate"]
                vehicle_id = memory["vehicle_id"]

                vehicle = (
                    db.query(Vehicle)
                    .filter(Vehicle.id == vehicle_id)
                    .first()
                )

                if not vehicle:
                    del agent_memory[sender_phone]
                    return reply_to_sender("Vehicle not found. Please send car image again.")

                customer = vehicle.customer

                if lower_msg == "no":
                    driver = get_or_create_driver(db, sender_phone)
                    otp = generate_otp()

                    create_or_update_session(
                        db=db,
                        vehicle_id=vehicle.id,
                        driver_id=driver.id,
                        otp=otp
                    )

                    del agent_memory[sender_phone]

                    otp_message = f"""Your vehicle {plate} is parked.
Your OTP is {otp}.
State: PARKED

When you need the car, send:
get my car"""

                    driver_message = f"""OTP/message sent successfully to customer {customer.name}.

Customer Number: {customer.phone}
Vehicle: {plate}
State: PARKED"""

                    return reply_and_send(
                        driver_message,
                        customer.phone,
                        otp_message
                    )

                if lower_msg == "yes":
                    agent_memory[sender_phone]["step"] = "waiting_new_phone"
                    return reply_to_sender("Please send the new customer phone number.")

                return reply_to_sender("Please reply YES or NO.")

            except Exception as e:
                print("WAITING_YES_NO ERROR:", e)
                db.rollback()
                return reply_to_sender("Something went wrong. Please send reset and try again.")

        # UPDATE CUSTOMER PHONE
        if step == "waiting_new_phone":
            try:
                new_phone = message.strip().replace(" ", "").replace("+91", "")

                if not new_phone.isdigit() or len(new_phone) != 10:
                    return reply_to_sender("Please send valid 10 digit phone number.")

                plate = memory["plate"]
                vehicle_id = memory["vehicle_id"]

                vehicle = (
                    db.query(Vehicle)
                    .filter(Vehicle.id == vehicle_id)
                    .first()
                )

                if not vehicle:
                    del agent_memory[sender_phone]
                    return reply_to_sender("Vehicle not found. Please send car image again.")

                customer = vehicle.customer

                existing_customer = (
                    db.query(Customer)
                    .filter(Customer.phone == new_phone)
                    .first()
                )

                if existing_customer and existing_customer.id != customer.id:
                    return reply_to_sender("This phone number is already registered.")

                customer.phone = new_phone
                db.commit()

                driver = get_or_create_driver(db, sender_phone)
                otp = generate_otp()

                create_or_update_session(
                    db=db,
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    otp=otp
                )

                del agent_memory[sender_phone]

                customer_msg = f"""Your vehicle {plate} is parked.
Your OTP is {otp}.
State: PARKED

When you need the car, send:
get my car"""

                driver_msg = f"""Customer phone number updated successfully.

Vehicle: {plate}
OTP/message sent to {new_phone}.
State: PARKED"""

                return reply_and_send(
                    driver_msg,
                    new_phone,
                    customer_msg
                )

            except Exception as e:
                print("WAITING_NEW_PHONE ERROR:", e)
                db.rollback()
                return reply_to_sender(f"DB Error: {str(e)[:200]}")

    # DRIVER SENDS IMAGE
    has_media = data.get("hasMedia", False)

    if has_media:
        media_base64 = data.get("mediaBase64")

        if not media_base64:
            return reply_to_sender("Image not received properly.")

        get_or_create_driver(db, sender_phone)

        plate_raw = extract_plate_from_image(media_base64)
        plate = extract_clean_plate(plate_raw)

        print("RAW PLATE:", plate_raw)
        print("FINAL PLATE:", plate)

        agent_memory[sender_phone] = {
            "step": "waiting_plate_confirmation",
            "plate": plate
        }

        return reply_to_sender(
            f"""Detected vehicle plate: {plate}

Reply YES to confirm
OR send correct plate number manually."""
        )

    return reply_to_sender("Message received but no matching flow found.")


@router.get("/test")
def test():
    return {
        "message": "SwiftValet whatsapp-web.js backend is running"
    }
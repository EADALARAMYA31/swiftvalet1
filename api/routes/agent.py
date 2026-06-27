from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
import random
import re

from api.db import SessionLocal
from api.models import Customer, Vehicle, ValetDriver, ParkingSession
from api.plate_extractor import extract_plate_from_image

router = APIRouter(prefix="/agent", tags=["SwiftValet Agent"])

# Thread-safe dictionary tracking operational state steps
agent_memory = {}

ALLOWED_COMMANDS = {"reset", "get my car", "picked", "delivered", "paid"}

# ---------------- DATABASE DEPENDENCY ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- UTILITY FUNCTIONS ----------------
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
    phone = phone.replace("@c.us", "").replace("+", "").replace(" ", "")
    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    return phone

def reply_to_sender(message):
    return {"reply": message}

# FIXED: Standardized payload output matching Node client expectations
def reply_and_send(reply, send_to, message):
    return {
        "reply": reply,
        "sendTo": wa_number(send_to),
        "message": message
    }

def extract_clean_plate(raw_text):
    raw_text = str(raw_text).upper()
    matches = re.findall(r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}", raw_text)
    if matches:
        return matches[0]
    cleaned = re.sub(r"[^A-Z0-9]", "", raw_text)
    return cleaned[:20] if cleaned else "PLATE_NOT_FOUND"

# ---------------- DOMAIN HELPERS ----------------
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
            ParkingSession.state.in_(["PARKED", "OTP_PENDING", "REQUESTED", "IN_RETRIEVAL"])
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

def continue_after_plate_confirmation(db, sender_phone, plate):
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()

    if not vehicle:
        agent_memory[sender_phone] = {
            "step": "waiting_customer_details",
            "plate": plate
        }
        return reply_to_sender(
            f"🚗 Vehicle {plate} is not registered.\n\nPlease send customer details in format:\nName, Phone"
        )

    customer = vehicle.customer
    agent_memory[sender_phone] = {
        "step": "waiting_yes_no",
        "plate": plate,
        "vehicle_id": vehicle.id
    }

    return reply_to_sender(
        f"📋 Vehicle {plate} is already registered.\n\nCustomer: {customer.name}\nPhone: {customer.phone}\n\nDo you want to change the phone number?\nReply YES or NO."
    )

# ---------------- WHATSAPP WEB AGENT ROUTE ----------------
@router.post("/whatsapp-web")
async def whatsapp_web_agent(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    sender_raw = data.get("from", "")
    sender_phone = normalize_phone(sender_raw)
    message = str(data.get("body", "")).strip()
    lower_msg = message.lower()
    has_media = data.get("hasMedia", False)

    # 1. Broad Systems Safety Gate
    if "@broadcast" in sender_raw or "@newsletter" in sender_raw or "@g.us" in sender_raw:
        return Response(status_code=200, content="")

    is_in_flow = sender_phone in agent_memory
    is_command = lower_msg in ALLOWED_COMMANDS
    is_otp = message.isdigit() and len(message) == 6

    # Protect personal chats completely
    if not (is_in_flow or is_command or is_otp or has_media):
        return Response(status_code=200, content="")

    # 2. RESET FLOW COMMAND
    if lower_msg == "reset":
        if sender_phone in agent_memory:
            del agent_memory[sender_phone]
        return reply_to_sender("🔄 Flow reset successfully. Please send car image.")

    # 3. IMAGE PROCESSING FLOW (Moved up so it catches early image signals safely)
    # 3. IMAGE PROCESSING FLOW
    if has_media:
        try:
            media_base64 = data.get("mediaBase64")
            if not media_base64:
                return reply_to_sender("❌ Image file payload data not received properly.")

            get_or_create_driver(db, sender_phone)
            
            print("🤖 Passing image data over to plate extractor layer...")
            plate_raw = extract_plate_from_image(media_base64)
            plate = extract_clean_plate(plate_raw)

            print("RAW PLATE DETECTED:", plate_raw)
            print("CLEANED PLATE:", plate)

            agent_memory[sender_phone] = {
                "step": "waiting_plate_confirmation",
                "plate": plate
            }

            return reply_to_sender(
                f"📸 Detected vehicle plate: {plate}\n\nReply *YES* to confirm or type the correct plate number manually."
            )
        except Exception as ocr_error:
            print("🚨 OCR ENGINE CRASHED:", str(ocr_error))
            return reply_to_sender(f"❌ Failed to process vehicle image. Error details: {str(ocr_error)[:100]}")

    # 4. ACTIVE MEMORY FLOWS (Registration handling blocks)
    if sender_phone in agent_memory:
        memory = agent_memory[sender_phone]
        step = memory["step"]

        if step == "waiting_plate_confirmation":
            plate = memory["plate"] if lower_msg == "yes" else extract_clean_plate(message)
            del agent_memory[sender_phone]
            return continue_after_plate_confirmation(db, sender_phone, plate)

        if step == "waiting_customer_details":
            try:
                parts = message.split(",")
                if len(parts) != 2:
                    return reply_to_sender("⚠️ Invalid format. Please reply with: Name, Phone")

                name = parts[0].strip()
                customer_phone = parts[1].strip().replace(" ", "").replace("+91", "")

                if not customer_phone.isdigit() or len(customer_phone) != 10:
                    return reply_to_sender("❌ Please send a valid 10-digit phone number.")

                plate = memory["plate"]
                driver = get_or_create_driver(db, sender_phone)

                customer = db.query(Customer).filter(Customer.phone == customer_phone).first()
                if not customer:
                    customer = Customer(name=name, phone=customer_phone)
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)

                existing_vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
                if existing_vehicle:
                    return reply_to_sender("⚠️ This vehicle registration already exists inside the system.")

                vehicle = Vehicle(plate_number=plate, customer_id=customer.id)
                db.add(vehicle)
                db.commit()
                db.refresh(vehicle)

                otp = generate_otp()
                create_or_update_session(db=db, vehicle_id=vehicle.id, driver_id=driver.id, otp=otp)
                del agent_memory[sender_phone]

                customer_msg = f"🎉 Welcome to SwiftValet.\n\nYour vehicle *{plate}* is safely parked.\n🔑 Your retrieval code is: {otp}.\n\nWhen you need your car back, simply send: *get my car*"
                driver_msg = f"✅ Customer registration successful.\n\nCustomer: {customer.name}\nVehicle *{plate}* linked with {customer_phone}.\nState: PARKED"

                return reply_and_send(reply=driver_msg, send_to=customer_phone, message=customer_msg)

            except Exception as e:
                db.rollback()
                return reply_to_sender(f"❌ System Processing Error: {str(e)}")

        if step == "waiting_yes_no":
            plate = memory["plate"]
            vehicle_id = memory["vehicle_id"]
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

            if not vehicle:
                del agent_memory[sender_phone]
                return reply_to_sender("❌ Error tracking vehicle. Please send car image again.")

            customer = vehicle.customer

            if lower_msg == "no":
                driver = get_or_create_driver(db, sender_phone)
                otp = generate_otp()
                create_or_update_session(db=db, vehicle_id=vehicle.id, driver_id=driver.id, otp=otp)
                del agent_memory[sender_phone]

                otp_message = f"🚗 Your vehicle *{plate}* has been parked.\n\nWhen you are ready, reply with: *get my car*"
                driver_message = f"✅ Session confirmed for customer {customer.name}.\n\nCustomer: {customer.phone}\nVehicle: {plate}\nState: PARKED"

                return reply_and_send(reply=driver_message, send_to=customer.phone, message=otp_message)

            if lower_msg == "yes":
                agent_memory[sender_phone]["step"] = "waiting_new_phone"
                return reply_to_sender("📱 Please send the new 10-digit customer phone number.")

            return reply_to_sender("⚠️ Please reply explicitly with YES or NO.")

        if step == "waiting_new_phone":
            try:
                new_phone = message.strip().replace(" ", "").replace("+91", "")
                if not new_phone.isdigit() or len(new_phone) != 10:
                    return reply_to_sender("❌ Please send a valid 10-digit phone number.")

                plate = memory["plate"]
                vehicle_id = memory["vehicle_id"]
                vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
                customer = vehicle.customer

                existing_customer = db.query(Customer).filter(Customer.phone == new_phone).first()
                if existing_customer and existing_customer.id != customer.id:
                    return reply_to_sender("⚠️ This phone number is already assigned to another profile.")

                customer.phone = new_phone
                db.commit()

                driver = get_or_create_driver(db, sender_phone)
                otp = generate_otp()
                create_or_update_session(db=db, vehicle_id=vehicle.id, driver_id=driver.id, otp=otp)
                del agent_memory[sender_phone]

                customer_msg = f"🚗 Your vehicle *{plate}* is parked.\n🔑 Your retrieval OTP is: {otp}.\n\nWhen ready, reply: *get my car*"
                driver_msg = f"✅ Customer profile updated.\n\nVehicle: {plate}\nOTP sent to updated number: {new_phone}.\nState: PARKED"

                return reply_and_send(reply=driver_msg, send_to=new_phone, message=customer_msg)
            except Exception as e:
                db.rollback()
                return reply_to_sender(f"❌ DB Error: {str(e)}")

    # 5. GET MY CAR COMMAND
    if "get my car" in lower_msg:
        session = db.query(ParkingSession).filter(ParkingSession.state == "PARKED").order_by(ParkingSession.id.desc()).first()
        if not session:
            return reply_to_sender("❌ No active parked vehicles found matching your session request.")

        vehicle = session.vehicle
        otp = generate_otp()
        session.otp = otp
        session.state = "OTP_PENDING"
        db.commit()

        return reply_to_sender(
            f"🎯 Retrieval request initiated for vehicle *{vehicle.plate_number}*.\n\n🔑 Your active verification OTP is: *{otp}*.\nReply with this 6-digit code to confirm."
        )

    # 6. OTP PROCESSING STAGE
    if message.isdigit() and len(message) == 6:
        session = db.query(ParkingSession).filter(ParkingSession.otp == message, ParkingSession.state == "OTP_PENDING").order_by(ParkingSession.id.desc()).first()
        if not session:
            return reply_to_sender("❌ Invalid or expired verification code.")

        session.state = "REQUESTED"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        customer_msg = f"✅ Code verified successfully.\n\nYour vehicle *{vehicle.plate_number}* retrieval request is queued.\nState: *REQUESTED*"
        driver_msg = f"👨‍✈️ Urgent: Customer {customer.name} requested vehicle *{vehicle.plate_number}*.\n\nPhone: {customer.phone}\nZone: {session.park_zone}\n\n👉 Reply *PICKED* when starting retrieval.\n👉 Reply *DELIVERED* upon handover."

        return reply_and_send(reply=customer_msg, send_to=session.driver.phone, message=driver_msg)

    # 7. DRIVER STATE: PICKED UP
    if lower_msg == "picked":
        driver = db.query(ValetDriver).filter(ValetDriver.phone == sender_phone).first()
        if not driver:
            return reply_to_sender("❌ Driver security authentication failed.")

        session = db.query(ParkingSession).filter(ParkingSession.driver_id == driver.id, ParkingSession.state == "REQUESTED").first()
        if not session:
            return reply_to_sender("⚠️ No active REQUESTED delivery schedules linked to your profile.")

        session.state = "IN_RETRIEVAL"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        driver_reply = f"✅ Vehicle *{vehicle.plate_number}* tracked as *IN_RETRIEVAL*.\n\nReply *DELIVERED* once given to customer."
        customer_msg = f"👨‍✈️ Your vehicle *{vehicle.plate_number}* is on its way!\n\nDriver has started retrieval process.\nState: *IN_RETRIEVAL*"

        return reply_and_send(reply=driver_reply, send_to=customer.phone, message=customer_msg)

    # 8. DRIVER STATE: DELIVERED
    if lower_msg == "delivered":
        driver = db.query(ValetDriver).filter(ValetDriver.phone == sender_phone).first()
        if not driver:
            return reply_to_sender("❌ Driver profile validation failed.")

        session = db.query(ParkingSession).filter(ParkingSession.driver_id == driver.id, ParkingSession.state == "IN_RETRIEVAL").first()
        if not session:
            return reply_to_sender("⚠️ No vehicles currently marked in retrieval for your profile.")

        session.state = "PAYMENT_PENDING"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        driver_reply = f"📦 Vehicle *{vehicle.plate_number}* marked as *DELIVERED*.\n\nState: PAYMENT_PENDING\nWaiting on customer payment verification."
        payment_msg = f"📦 Your vehicle *{vehicle.plate_number}* has arrived at the pick-up station.\n\n💰 Please settle the balance via the link below:\n`upi://pay?pa=swiftvalet@upi&pn=SwiftValet&am=100`\n\nReply *PAID* directly after submitting transaction."

        return reply_and_send(reply=driver_reply, send_to=customer.phone, message=payment_msg)

    # 9. CUSTOMER PAYMENT SENSE
    if lower_msg == "paid":
        session = db.query(ParkingSession).filter(ParkingSession.state == "PAYMENT_PENDING").order_by(ParkingSession.id.desc()).first()
        if not session:
            return reply_to_sender("❌ No structural transaction awaiting payment found.")

        session.state = "PAID_AND_EXITED"
        db.commit()

        vehicle = session.vehicle
        customer = vehicle.customer

        customer_msg = f"🎉 Payment accepted successfully!\n\nVehicle *{vehicle.plate_number}* session closed out.\nState: *PAID_AND_EXITED*\n\nThank you for choosing SwiftValet!"
        driver_msg = f"💰 Payment verified for vehicle *{vehicle.plate_number}*.\n\nCustomer: {customer.name}\nState: *PAID_AND_EXITED*\n\nValet mission complete."

        return reply_and_send(reply=customer_msg, send_to=session.driver.phone, message=driver_msg)

    return Response(status_code=200, content="")


@router.get("/test")
def test():
    return {"message": "SwiftValet backend running"}
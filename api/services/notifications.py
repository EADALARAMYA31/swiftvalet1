def notify_driver(driver, session):
    message = f"""
🚗 NEW JOB ASSIGNED

Vehicle: {session.vehicle.plate_number}
Zone: {session.park_zone}

Reply:
PICKED {session.id} → when you take the car
"""
    
    print("Send WhatsApp to driver:", driver.phone)
    print(message)
def notify_customer(session, message):
    phone = session.vehicle.customer.phone

    print("Send WhatsApp to customer:", phone)
    print(message)
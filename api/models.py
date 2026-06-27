from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from api.db import Base
from sqlalchemy import DateTime
from datetime import datetime


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)

    vehicles = relationship("Vehicle", back_populates="customer")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))

    customer = relationship("Customer", back_populates="vehicles")
    sessions = relationship("ParkingSession", back_populates="vehicle")


class ValetDriver(Base):
    __tablename__ = "valet_drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    pin = Column(String)

    status = Column(String, default="FREE")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    active_jobs = Column(Integer, default=0)   # ✅ ADD THIS

    sessions = relationship("ParkingSession", back_populates="driver")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    driver_id = Column(Integer, ForeignKey("valet_drivers.id"), nullable=True)

    state = Column(String, default="PARKED")
    otp = Column(String, nullable=True)
    park_zone = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    vehicle = relationship("Vehicle", back_populates="sessions")
    driver = relationship("ValetDriver", back_populates="sessions")
    events = relationship(
    "SessionEvent",
    back_populates="session",
    cascade="all, delete"
    )
class SessionEvent(Base):

    __tablename__ = "session_events"

    id = Column(Integer, primary_key=True)

    session_id = Column(
        Integer,
        ForeignKey("parking_sessions.id")
    )

    event = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    session = relationship(
        "ParkingSession",
        back_populates="events"
    )
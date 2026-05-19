from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from api.db import Base


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

    sessions = relationship("ParkingSession", back_populates="driver")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    driver_id = Column(Integer, ForeignKey("valet_drivers.id"), nullable=True)

    state = Column(String, default="PARKED")
    otp = Column(String, nullable=True)
    park_zone = Column(String, nullable=True)

    vehicle = relationship("Vehicle", back_populates="sessions")
    driver = relationship("ValetDriver", back_populates="sessions")
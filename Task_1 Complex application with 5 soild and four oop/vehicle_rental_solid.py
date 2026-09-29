"""
COMPLEX APPLICATION: Vehicle Rental System
Demonstrates all 4 OOP pillars + SOLID principles (SRP, OCP, LSP, ISP, DIP).
Run: python vehicle_rental_solid.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

#
# ===========================================================================
# ABSTRACTION + inheritance base — also the hook for OCP (Open/Closed)
# New vehicle types can be added later WITHOUT modifying this class or the
# RentalSystem that uses it. this is a desgin choice foe me . please undertand this insutcor 
# ===========================================================================
class Vehicle(ABC):
    def __init__(self, plate: str, daily_rate: float):
        self.plate = plate
        self._daily_rate = daily_rate          # ENCAPSULATION: protected field
        self.__mileage = 0                      # ENCAPSULATION: private field

    @property
    def mileage(self) -> int:
        return self.__mileage

    def add_mileage(self, km: int) -> None:
        if km < 0:
            raise ValueError("Mileage cannot decrease")
        self.__mileage += km

    @abstractmethod
    def calculate_rental_cost(self, days: int) -> float:
        """Each vehicle type prices itself differently (POLYMORPHISM)."""
        ...

    @abstractmethod
    def vehicle_type(self) -> str:
        ...


# ---------------------------------------------------------------------------
# ISP (Interface Segregation): separate, focused interfaces rather than one
# fat "Vehicle" interface that forces every class to implement things it
# doesn't need (e.g. not all vehicles are insurable the same way).
# ---------------------------------------------------------------------------
class Insurable(ABC):
    @abstractmethod
    def insurance_cost(self, days: int) -> float:
        ...


# ===========================================================================
# INHERITANCE: concrete vehicle types extend Vehicle.
# Each override still honours the Vehicle contract, so any of them can be
# substituted wherever a Vehicle is expected (LSP — Liskov Substitution).
# ===========================================================================
class Car(Vehicle, Insurable):
    def vehicle_type(self) -> str:
        return "Car"

    def calculate_rental_cost(self, days: int) -> float:
        return self._daily_rate * days

    def insurance_cost(self, days: int) -> float:
        return 5.0 * days


class Motorcycle(Vehicle):
    def vehicle_type(self) -> str:
        return "Motorcycle"

    def calculate_rental_cost(self, days: int) -> float:
        return self._daily_rate * days * 0.8   # cheaper per day than a car


class Truck(Vehicle, Insurable):
    def __init__(self, plate: str, daily_rate: float, capacity_tons: float):
        super().__init__(plate, daily_rate)
        self.capacity_tons = capacity_tons

    def vehicle_type(self) -> str:
        return "Truck"

    def calculate_rental_cost(self, days: int) -> float:
        base = self._daily_rate * days
        surcharge = self.capacity_tons * 2 * days
        return base + surcharge

    def insurance_cost(self, days: int) -> float:
        return 15.0 * days


# To extend the system with, e.g., an ElectricVan, you would add a new class
# below — no existing class needs to change. That is OCP in action.
class ElectricVan(Vehicle):
    def vehicle_type(self) -> str:
        return "Electric Van"

    def calculate_rental_cost(self, days: int) -> float:
        return self._daily_rate * days * 0.9   # eco discount


# ===========================================================================
# DIP (Dependency Inversion): RentalSystem depends on the PaymentProcessor
# ABSTRACTION, not on a concrete payment class. Concrete processors are
# injected, so payment logic can change without touching RentalSystem.
# ===========================================================================
class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float) -> bool:
        ...


class CardPaymentProcessor(PaymentProcessor):
    def process(self, amount: float) -> bool:
        print(f"[Card] Charged AED {amount:.2f}")
        return True


class CashPaymentProcessor(PaymentProcessor):
    def process(self, amount: float) -> bool:
        print(f"[Cash] Received AED {amount:.2f}")
        return True


# ---------------------------------------------------------------------------
# SRP (Single Responsibility): each class below has exactly one reason to
# change — notifications, receipts, and orchestration are kept separate
# instead of being crammed into one "God class".
# ---------------------------------------------------------------------------
class NotificationService:
    def send(self, message: str) -> None:
        print(f"[Notification] {message}")


class ReceiptService:
    def generate(self, plate: str, vehicle_type: str, days: int, total: float) -> str:
        return (f"--- Receipt ---\n"
                f"Vehicle: {vehicle_type} ({plate})\n"
                f"Duration: {days} day(s)\n"
                f"Total: AED {total:.2f}\n"
                f"----------------")


@dataclass
class RentalAgreement:
    vehicle: Vehicle
    days: int
    start_date: date = field(default_factory=date.today)


class RentalSystem:
    """
    Orchestrator only — it does NOT know how payment is processed (DIP),
    does NOT format receipts, and does NOT send notifications itself.
    It just coordinates the collaborators it was given (SRP).
    """
    def __init__(self, payment_processor: PaymentProcessor,
                 notifier: NotificationService,
                 receipts: ReceiptService):
        self._payment_processor = payment_processor
        self._notifier = notifier
        self._receipts = receipts

    def rent(self, agreement: RentalAgreement) -> str:
        vehicle = agreement.vehicle
        cost = vehicle.calculate_rental_cost(agreement.days)   # POLYMORPHISM

        if isinstance(vehicle, Insurable):                      # ISP in use
            cost += vehicle.insurance_cost(agreement.days)

        self._payment_processor.process(cost)                   # DIP in use
        self._notifier.send(f"Rental confirmed for {vehicle.plate}")
        return self._receipts.generate(vehicle.plate, vehicle.vehicle_type(),
                                        agreement.days, cost)


if __name__ == "__main__":
    fleet = [
        Car("DXB-101", daily_rate=120),
        Motorcycle("DXB-202", daily_rate=60),
        Truck("DXB-303", daily_rate=200, capacity_tons=3),
        ElectricVan("DXB-404", daily_rate=140),   # added with zero changes elsewhere
    ]

    system = RentalSystem(
        payment_processor=CardPaymentProcessor(),   # swap for CashPaymentProcessor freely
        notifier=NotificationService(),
        receipts=ReceiptService(),
    )

    for v in fleet:
        agreement = RentalAgreement(vehicle=v, days=3)
        print(system.rent(agreement))
        print()

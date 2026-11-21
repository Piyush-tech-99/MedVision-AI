
from getpass import getpass

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def create_doctor():
    db = SessionLocal()

    try:
        print("\n===== MedVision AI | Create Doctor Account =====\n")

        name = input("Doctor name: ").strip()
        email = input("Doctor email: ").strip().lower()

        if len(name) < 2 or len(name) > 150:
            print("Error: Name must contain 2-150 characters.")
            return

        if "@" not in email or len(email) > 255:
            print("Error: Enter a valid email address.")
            return

        existing_user = db.query(User).filter(
            User.email == email
        ).first()

        if existing_user:
            print("Error: An account with this email already exists.")
            return

        password = getpass("Create password: ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            print("Error: Passwords do not match.")
            return

        if len(password) < 8:
            print("Error: Password must contain at least 8 characters.")
            return

        if len(password.encode("utf-8")) > 72:
            print("Error: Password cannot exceed 72 bytes.")
            return

        doctor = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            role="doctor"
        )

        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        print("\nDoctor account created successfully!")
        print("--------------------------------------")
        print(f"Doctor ID: {doctor.id}")
        print(f"Name: {doctor.name}")
        print(f"Email: {doctor.email}")
        print(f"Role: {doctor.role}")
        print("--------------------------------------")

    except Exception as error:
        db.rollback()
        print(f"\nCould not create doctor account: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    create_doctor()

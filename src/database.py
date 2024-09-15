import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, create_engine, select

from . import models

# sqlite_url = "sqlite:///data.db"
sqlite_url = "sqlite://"

engine = create_engine(sqlite_url, echo=True)


def append_sample_data(session: Session) -> None:
    """Write sample data to the database on system startup."""
    create_sample_customers(session)
    create_sample_orders(session)
    assert len(session.exec(select(models.Customer)).all()) > 0
    assert len(session.exec(select(models.Order)).all()) > 0


def create_sample_customers(session: Session) -> None:
    customers = [
        models.Customer(
            name="Giorikas", surname="Alpha", contact_email="giorikas@alpha.com"
        ),
        models.Customer(
            name="Kostikas", surname="Giota", contact_email="kostikas@giota.com"
        ),
        models.Customer(name="Makis", surname="Zita", contact_email="makis@zita.com"),
        models.Customer(
            name="Fotis", surname="ParaPente", contact_email="fotis@parapente.com"
        ),
    ]

    try:
        for customer in customers:
            session.add(customer)
    except Exception as e:
        print(e)
        session.rollback()
    finally:
        session.commit()


def create_sample_orders(session: Session) -> None:
    orders = [
        models.Order(
            initialized=int(
                (datetime.now() - timedelta(days=random.randint(0, 50))).timestamp()
            ),
            amount=Decimal(random.random() * 100 - 1),
            currency=random.choice(list(models.CurrencyEnum)),
            finalized=None,
            customer_id=random.randint(1, 4),
        )
        for _ in range(20)
    ]

    try:
        for order in orders:
            session.add(order)
    except Exception as e:
        print(e)
        session.rollback()
    finally:
        session.commit()

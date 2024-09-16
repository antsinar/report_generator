import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from os import environ
from pathlib import Path
from typing import Generator, List, Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import select, text
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from .database import Session, SQLModel, append_sample_data, engine
from .models import ORDER_PREFIX, CurrencyEnum
from .models import Order as dbOrder
from .template_utils import datetime_format, handle_none, timestamp_format


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = find_dotenv(".env")
    load_dotenv(env)
    (Path(__file__).parent / "reports").mkdir(exist_ok=True)
    if environ.get("MAINTENANCE", "False") == "False":
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.exec(text("PRAGMA journal_mode=WAL;"))
            session.commit()
            append_sample_data(session)
    yield


@contextmanager
def db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        try:
            yield session
        except Exception as e:
            print(e)
            session.rollback()
        finally:
            session.commit()


app = FastAPI(lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=3000, compresslevel=7)


@app.middleware("http")
async def redirect_to_maintenance(request: Request, call_next):
    if environ.get("MAINTENANCE", "False") == "False":
        return await call_next(request)
    response = JSONResponse(
        status_code=200, content={"message": "Server Unavailable due to maintenance"}
    )
    response.headers["X-Server-Mode"] = "Maintenance Mode"
    return response


jinja_env = Environment(loader=PackageLoader("src"), autoescape=select_autoescape())
jinja_env.filters["dt_format"] = datetime_format
jinja_env.filters["ts_format"] = timestamp_format
jinja_env.filters["handle_none"] = handle_none


class BaseOrder(BaseModel):
    uid: int
    name: str
    surname: str
    initialized: int

    @property
    def uid_with_prefix(self) -> str:
        return f"{ORDER_PREFIX}{self.uid}"


class Order(BaseOrder):
    amount: Optional[Decimal] = Field(default=None)
    currency: CurrencyEnum = Field(default=CurrencyEnum.EUR)
    finalized: Optional[int] = Field(default=None)


class BaseReport(BaseModel):
    uid: uuid.UUID = Field(default_factory=lambda: uuid.uuid4())

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Report(BaseReport):
    content: Optional[bytes] = Field(default=None)


@app.get("/")
async def root():
    return RedirectResponse("/docs")


@app.post("/queue-report/")
async def queue_report(background_tasks: BackgroundTasks) -> Report:
    """Initialize pdf generation
    Return report uuid to use to get the result
    """
    report = Report()
    background_tasks.add_task(generate_report, uid=report.uid)
    return report


@app.get("/reports")
async def get_all_reports() -> List[str]:
    return [
        item.stem
        for item in (Path(__file__).parent / "reports").iterdir()
        if item.is_file() and item.suffix == ".pdf"
    ]


@app.get("/get-report/{uid}/")
async def get_report(uid: uuid.UUID):
    """Return Generated Report PDF from list of orders"""
    report_bytes: Optional[BytesIO] = await get_report_from_storage(uid)
    if not report_bytes:
        return JSONResponse(
            status_code=404, content={"reason": f"Report with id {uid} not found."}
        )
    return Response(
        content=report_bytes.getvalue(),
        status_code=200,
        headers={
            "Content-Disposition": 'attachment; filename="report.pdf"',
            "Accept-Encoding": "gzip",
        },
        media_type="application/pdf",
    )


def gather_orders() -> List[Order]:
    with db_session() as session:
        results = session.exec(select(dbOrder).order_by(-dbOrder.initialized)).all()
        print("Results: ", len(results))
        return [
            Order(
                uid=order.uid,
                name=order.customer.name,
                surname=order.customer.surname,
                amount=order.amount,
                currency=order.currency,
                initialized=order.initialized,
                finalized=order.finalized,
            )
            for order in results
        ]


def generate_report(uid: uuid.UUID) -> None:
    template = jinja_env.get_template("base.html")
    context = {
        "when": (datetime.now(timezone.utc).astimezone() + timedelta(hours=3)),
        "data": gather_orders(),
    }
    font_config = FontConfiguration()
    css = CSS(string="@page {margin: 1.5cm;}", font_config=font_config)
    HTML(string=template.render(context)).write_pdf(
        Path(__file__).parent / f"reports/{uid}.pdf",
        stylesheets=[
            css,
            Path(__file__).parent / "templates/style.css",
        ],
        font_config=font_config,
    )


async def get_report_from_storage(uid: uuid.UUID) -> Optional[BytesIO]:
    """Return the body of the pdf report, if it exists"""
    target_file = Path(__file__).parent / f"reports/{uid}.pdf"
    if (target_file).exists():
        return BytesIO(target_file.read_bytes())
    return None

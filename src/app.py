import json
import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, Response
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from io import BytesIO
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from jinja2 import Environment, PackageLoader, select_autoescape
from functools import partial
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .template_utils import datetime_format, timestamp_format, handle_none


app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=3000, compresslevel=7)

jinja_env = Environment(loader=PackageLoader("src"), autoescape=select_autoescape())
jinja_env.filters["dt_format"] = datetime_format
jinja_env.filters["ts_format"] = timestamp_format
jinja_env.filters["handle_none"] = handle_none


class CurrencyEnum(StrEnum):
    EU = "€"
    USD = "$"
    TL = "₺"


class BaseOrder(BaseModel):
    uid: str
    name: str
    surname: str
    initialized: int


class Order(BaseOrder):
    amount: Optional[Decimal] = Field(default=None)
    currency: CurrencyEnum = Field(default=CurrencyEnum.EU)
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
    background_tasks.add_task(make_pdf, uid=report.uid)
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
    orders = json.loads((Path(__file__).parent / "data.json").read_text())
    return [Order(**val) for val in orders.values()]


def generate_report(orders: List[Order], uid: uuid.UUID) -> None:
    template = jinja_env.get_template("base.html")
    context = {
        "when": (datetime.now(timezone.utc).astimezone() + timedelta(hours=3)),
        "data": orders,
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


make_pdf = partial(generate_report, gather_orders())


async def get_report_from_storage(uid: uuid.UUID) -> Optional[BytesIO]:
    """Return the body of the pdf report, if it exists"""
    target_file = Path(__file__).parent / f"reports/{uid}.pdf"
    if (target_file).exists():
        return BytesIO(target_file.read_bytes())
    return None

"""Aplicacion local para consultar Estimates de HighLevel y generar PDFs.

Solo usa la biblioteca estandar de Python para el servidor y ReportLab para PDF.
El Private Integration Token permanece en el servidor y nunca se envia al navegador.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import textwrap
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:
    print("Falta ReportLab. Instala con: python -m pip install reportlab", file=sys.stderr)
    raise


FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) if FROZEN else APP_DIR
CONFIG_PATH = APP_DIR / "config.local.json"
STATIC_PATH = RESOURCE_DIR / "static" / "index.html"
DEMO_PATH = RESOURCE_DIR / "demo-estimates.json"
API_BASE = "https://services.leadconnectorhq.com"
VERSION = "v3"


def load_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["location_id"] = os.getenv("GHL_LOCATION_ID", config.get("location_id", ""))
    config["token"] = os.getenv("GHL_PRIVATE_TOKEN", config.get("token", ""))
    config["port"] = int(os.getenv("PORT", config.get("port", 8765)))
    return config


def strip_html(value: Any) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


def esc(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def money(value: Any, currency: str) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"${number:,.2f} {currency}"


def readable_date(value: Any) -> str:
    if not value:
        return "-"
    raw = str(value)[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return raw


def estimate_id(item: dict[str, Any]) -> str:
    return str(item.get("_id") or item.get("id") or "")


class HighLevelClient:
    def __init__(self, location_id: str, token: str):
        self.location_id = location_id
        self.token = token

    @property
    def configured(self) -> bool:
        return bool(self.location_id and self.token)

    def list_estimates(
        self, status: str = "draft", contact_id: str = "", search: str = ""
    ) -> list[dict[str, Any]]:
        if not self.configured:
            return json.loads(DEMO_PATH.read_text(encoding="utf-8"))["estimates"]

        query: dict[str, str] = {
            "altId": self.location_id,
            "altType": "location",
            "status": status or "all",
            "limit": "100",
            "offset": "0",
        }
        if contact_id:
            query["contactId"] = contact_id
        if search:
            query["search"] = search
        url = f"{API_BASE}/invoices/estimate/list?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "HighLevel-Estimates-PDF/1.0",
                "Version": VERSION,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403 and ("error 1010" in detail.lower() or "browser_signature_banned" in detail.lower()):
                raise RuntimeError(
                    "Cloudflare rechazo la firma HTTP del cliente (Error 1010). "
                    "El programa ya envio un User-Agent explicito; reinicialo para aplicar el cambio. "
                    "Si persiste, la IP o el software de seguridad de esta red esta siendo bloqueado "
                    "y debe probarse desde otra red o solicitar revision a soporte de HighLevel, "
                    "incluyendo el Ray ID mostrado en el error."
                ) from exc
            raise RuntimeError(f"HighLevel respondio {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"No fue posible conectar con HighLevel: {exc.reason}") from exc

        estimates = payload.get("estimates", []) if isinstance(payload, dict) else []
        if not isinstance(estimates, list):
            raise RuntimeError("La respuesta de HighLevel no contiene una lista de estimates.")
        objects = [item for item in estimates if isinstance(item, dict)]
        if estimates and not objects:
            raise RuntimeError(
                "La API devolvio identificadores sin detalle. Guarda la respuesta del endpoint "
                "Create Estimate o ajusta el adaptador a la respuesta real de tu cuenta."
            )
        return objects


def address_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    parts = [
        value.get("addressLine1"),
        value.get("addressLine2"),
        value.get("city"),
        value.get("state"),
        value.get("postalCode"),
        value.get("countryCode"),
    ]
    return ", ".join(str(part) for part in parts if part)


def calculate_totals(estimate: dict[str, Any]) -> tuple[float, float, float, float]:
    subtotal = 0.0
    taxes_total = 0.0
    for item in estimate.get("items", []) or []:
        qty = float(item.get("qty") or 0)
        amount = float(item.get("amount") or 0)
        line = qty * amount
        subtotal += line
        if not item.get("taxInclusive"):
            for tax in item.get("taxes", []) or []:
                taxes_total += line * float(tax.get("rate") or 0) / 100

    discount_data = estimate.get("discount") or {}
    discount_value = float(discount_data.get("value") or 0)
    discount = (
        subtotal * discount_value / 100
        if discount_data.get("type") == "percentage"
        else discount_value
    )
    provided_total = estimate.get("total")
    total = float(provided_total) if provided_total is not None else subtotal - discount + taxes_total
    return subtotal, discount, taxes_total, total


def build_pdf(estimate: dict[str, Any]) -> bytes:
    output = BytesIO()
    business = estimate.get("businessDetails") or {}
    contact = estimate.get("contactDetails") or {}
    currency = str(estimate.get("currency") or "MXN")
    subtotal, discount, taxes_total, total = calculate_totals(estimate)
    number = f"{estimate.get('estimateNumberPrefix') or 'COT-'}{estimate.get('estimateNumber') or ''}"

    doc = BaseDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Cotizacion {number}",
        author=str(business.get("name") or "Empresa"),
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
        canvas.setFillColor(colors.HexColor("#66788A"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 9 * mm, "Documento informativo - No constituye CFDI")
        canvas.drawRightString(192 * mm, 9 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="quote", frames=[frame], onPage=footer)])
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], textColor=colors.HexColor("#113B5C"), fontSize=22, leading=26, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#40566B")))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=12))
    styles.add(ParagraphStyle(name="SmallRight", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="TableHead", parent=styles["Small"], textColor=colors.white, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="TableHeadRight", parent=styles["TableHead"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#113B5C"), spaceBefore=8, spaceAfter=5))

    story: list[Any] = []
    header = Table(
        [
            [Paragraph(esc(business.get("name") or "MI EMPRESA"), styles["Brand"]), Paragraph("COTIZACION", styles["Brand"])],
            [Paragraph(esc(address_text(business.get("address"))), styles["Meta"]), Paragraph(f"<b>{esc(number)}</b>", styles["SmallRight"])],
            [Paragraph(esc(business.get("phoneNo") or ""), styles["Meta"]), Paragraph(f"Emisión: {readable_date(estimate.get('issueDate'))}<br/>Vigencia: {readable_date(estimate.get('expiryDate'))}", styles["SmallRight"])],
        ],
        colWidths=[110 * mm, 64 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([header, Spacer(1, 9 * mm), Paragraph("CLIENTE", styles["Section"])])

    client_rows = [
        ["Nombre / razón social", contact.get("name") or "-"],
        ["Empresa", contact.get("companyName") or "-"],
        ["Correo", contact.get("email") or "-"],
        ["Teléfono", contact.get("phoneNo") or "-"],
        ["Domicilio", address_text(contact.get("address")) or "-"],
    ]
    custom_fields = contact.get("customFields") or []
    for field in custom_fields[:6]:
        if isinstance(field, dict):
            client_rows.append([field.get("name") or "Dato", field.get("value") or "-"])
    client_table = Table([[Paragraph(f"<b>{esc(a)}</b>", styles["Small"]), Paragraph(esc(b), styles["Small"])] for a, b in client_rows], colWidths=[43 * mm, 131 * mm])
    client_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF3F7")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D4DE")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.extend([client_table, Spacer(1, 7 * mm), Paragraph("CONCEPTOS", styles["Section"])])

    item_rows: list[list[Any]] = [[
        Paragraph("Descripción", styles["TableHead"]),
        Paragraph("Cant.", styles["TableHeadRight"]),
        Paragraph("Precio", styles["TableHeadRight"]),
        Paragraph("Importe", styles["TableHeadRight"]),
    ]]
    for item in estimate.get("items", []) or []:
        qty = float(item.get("qty") or 0)
        amount = float(item.get("amount") or 0)
        description = esc(item.get("name") or "Concepto")
        detail = strip_html(item.get("description"))
        if detail:
            description += f"<br/><font color='#66788A'>{esc(detail)}</font>"
        item_rows.append([
            Paragraph(description, styles["Small"]),
            Paragraph(f"{qty:g}", styles["SmallRight"]),
            Paragraph(money(amount, currency), styles["SmallRight"]),
            Paragraph(money(qty * amount, currency), styles["SmallRight"]),
        ])
    item_table = Table(item_rows, colWidths=[91 * mm, 18 * mm, 32 * mm, 33 * mm], repeatRows=1)
    item_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#113B5C")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D4DE")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(item_table)

    total_rows = [
        ["Subtotal", money(subtotal, currency)],
        ["Descuento", f"- {money(discount, currency)}"],
        ["Impuestos", money(taxes_total, currency)],
        ["TOTAL", money(total, currency)],
    ]
    totals = Table([[Paragraph(f"<b>{esc(a)}</b>", styles["SmallRight"]), Paragraph(f"<b>{esc(b)}</b>", styles["SmallRight"])] for a, b in total_rows], colWidths=[38 * mm, 42 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#113B5C")), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F1F6")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([Spacer(1, 4 * mm), totals])

    terms = strip_html(estimate.get("termsNotes"))
    if terms:
        safe_terms = "<br/>".join(esc(line) for line in textwrap.wrap(terms, width=110, replace_whitespace=False))
        story.extend([Spacer(1, 7 * mm), Paragraph("TERMINOS Y OBSERVACIONES", styles["Section"]), Paragraph(safe_terms, styles["Small"])])

    doc.build(story)
    return output.getvalue()


CONFIG = load_config()
CLIENT = HighLevelClient(CONFIG["location_id"], CONFIG["token"])
CACHE: dict[str, dict[str, Any]] = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            data = STATIC_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == "/api/config":
            self.send_json({"mode": "highlevel" if CLIENT.configured else "demo", "locationConfigured": bool(CONFIG["location_id"])})
            return

        if parsed.path == "/api/estimates":
            params = urllib.parse.parse_qs(parsed.query)
            try:
                estimates = CLIENT.list_estimates(
                    status=params.get("status", ["draft"])[0],
                    contact_id=params.get("contactId", [""])[0].strip(),
                    search=params.get("search", [""])[0].strip(),
                )
                CACHE.clear()
                CACHE.update({estimate_id(item): item for item in estimates if estimate_id(item)})
                self.send_json({"estimates": estimates, "mode": "highlevel" if CLIENT.configured else "demo"})
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return

        match = re.fullmatch(r"/api/estimates/([^/]+)/pdf", parsed.path)
        if match:
            item = CACHE.get(urllib.parse.unquote(match.group(1)))
            if not item:
                self.send_json({"error": "Cotizacion no encontrada. Actualiza la lista primero."}, 404)
                return
            pdf = build_pdf(item)
            filename = re.sub(r"[^A-Za-z0-9_-]+", "-", item.get("name") or "cotizacion") + ".pdf"
            download = urllib.parse.parse_qs(parsed.query).get("download", ["0"])[0] == "1"
            disposition = "attachment" if download else "inline"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
            self.send_header("Content-Length", str(len(pdf)))
            self.end_headers()
            self.wfile.write(pdf)
            return

        self.send_json({"error": "Ruta no encontrada"}, 404)


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main() -> None:
    try:
        server = ExclusiveThreadingHTTPServer(("127.0.0.1", CONFIG["port"]), Handler)
    except OSError as exc:
        print(
            f"No se pudo iniciar: el puerto {CONFIG['port']} ya esta ocupado. "
            "Cierra la ventana anterior o termina el proceso que ejecuta app.py.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    mode = "HighLevel" if CLIENT.configured else "demo"
    print(f"Servidor iniciado en http://127.0.0.1:{CONFIG['port']} (modo {mode})")
    print("Presiona Ctrl+C para detenerlo.")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{CONFIG['port']}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()

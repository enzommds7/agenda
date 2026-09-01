"""
=============================================================
  Monitor de Logs com Geração de Relatório PDF
  Portal Orquestrador RPA - DBSA
=============================================================
  Descrição:
    Monitora uma pasta de logs em tempo real.
    Ao detectar erros (ERROR, CRITICAL, EXCEPTION, FATAL),
    gera automaticamente um relatório PDF formatado.

  Dependências:
    pip install watchdog reportlab

  Uso:
    python monitor_logs.py

  Configuração:
    Edite a seção CONFIG abaixo conforme necessário.
=============================================================
"""

import os
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


# ─────────────────────────────────────────────────────────────
#  CONFIG — Ajuste conforme o seu ambiente
# ─────────────────────────────────────────────────────────────
CONFIG = {
    # Pasta onde estão os arquivos de log a monitorar
    "log_dir": "./logs",

    # Pasta onde os PDFs gerados serão salvos
    "output_dir": "./relatorios",

    # Extensões de arquivo de log monitoradas
    "log_extensions": [".log", ".txt"],

    # Palavras-chave que indicam erro (case-insensitive)
    "error_keywords": ["ERROR", "CRITICAL", "EXCEPTION", "FATAL", "TRACEBACK"],

    # Quantidade mínima de novos erros para disparar a geração do PDF
    "min_errors_to_trigger": 1,

    # Nome da empresa no cabeçalho do PDF
    "company_name": "DBSA",

    # Cooldown em segundos entre relatórios do mesmo arquivo
    # (evita múltiplos PDFs para um arquivo que muda muito rápido)
    "cooldown_seconds": 30,
}
# ─────────────────────────────────────────────────────────────


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LogMonitor")


# ──────────────────────────────────────────────
#  Extração de erros do arquivo de log
# ──────────────────────────────────────────────

def extract_errors(filepath: str, keywords: list) -> list:
    """Lê o arquivo de log e retorna linhas com erros encontrados."""
    errors = []
    pattern = re.compile(
        "|".join(re.escape(kw) for kw in keywords),
        re.IGNORECASE,
    )
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.rstrip()
                if pattern.search(line):
                    # Tenta identificar o nível do erro
                    level = "ERROR"
                    for kw in ["CRITICAL", "FATAL", "EXCEPTION", "TRACEBACK"]:
                        if kw.lower() in line.lower():
                            level = kw
                            break

                    errors.append({
                        "line": line_num,
                        "level": level,
                        "message": line,
                        "timestamp": _extract_timestamp(line),
                    })
    except Exception as e:
        logger.error(f"Falha ao ler {filepath}: {e}")
    return errors


def _extract_timestamp(line: str) -> str:
    """Tenta extrair timestamp da linha de log."""
    patterns = [
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",
        r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}",
    ]
    for p in patterns:
        m = re.search(p, line)
        if m:
            return m.group()
    return "—"


# ──────────────────────────────────────────────
#  Geração do PDF
# ──────────────────────────────────────────────

LEVEL_COLORS = {
    "CRITICAL": colors.HexColor("#C0392B"),
    "FATAL":    colors.HexColor("#C0392B"),
    "ERROR":    colors.HexColor("#E74C3C"),
    "EXCEPTION":colors.HexColor("#E67E22"),
    "TRACEBACK":colors.HexColor("#8E44AD"),
}

LEVEL_BG = {
    "CRITICAL": colors.HexColor("#FADBD8"),
    "FATAL":    colors.HexColor("#FADBD8"),
    "ERROR":    colors.HexColor("#FDECEA"),
    "EXCEPTION":colors.HexColor("#FEF5EC"),
    "TRACEBACK":colors.HexColor("#F5EEF8"),
}


def generate_pdf(log_file: str, errors: list, output_dir: str, company: str) -> str:
    """Gera o PDF de relatório de erros e retorna o caminho do arquivo gerado."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_basename = Path(log_file).stem
    pdf_path = os.path.join(output_dir, f"relatorio_erros_{log_basename}_{ts}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Relatório de Erros — {log_basename}",
        author=company,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Estilos customizados ──
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#1A252F"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#5D6D7E"),
        spaceAfter=2,
        fontName="Helvetica",
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1A5276"),
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#2C3E50"),
        fontName="Helvetica",
        leading=13,
    )
    code_style = ParagraphStyle(
        "Code",
        parent=styles["Normal"],
        fontSize=7.5,
        fontName="Courier",
        textColor=colors.HexColor("#212121"),
        leading=11,
        wordWrap="CJK",
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#7F8C8D"),
        fontName="Helvetica",
        alignment=TA_RIGHT,
    )

    # ── Cabeçalho ──
    story.append(Paragraph("Relatorio de Erros de Sistema", title_style))
    story.append(Paragraph(f"{company} - Portal Orquestrador RPA", subtitle_style))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M:%S')}",
        meta_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1A5276"), spaceAfter=12))

    # ── Sumário Executivo ──
    story.append(Paragraph("Sumario Executivo", section_style))

    level_counts = defaultdict(int)
    for e in errors:
        level_counts[e["level"]] += 1

    summary_data = [
        ["Metrica", "Valor"],
        ["Arquivo monitorado", Path(log_file).name],
        ["Total de erros encontrados", str(len(errors))],
        ["Primeira ocorrencia", errors[0]["timestamp"] if errors else "—"],
        ["Ultima ocorrencia", errors[-1]["timestamp"] if errors else "—"],
    ]
    for level, count in sorted(level_counts.items()):
        summary_data.append([f"  -> {level}", str(count)])

    summary_table = Table(summary_data, colWidths=[9 * cm, 8 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1A5276")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EBF5FB"), colors.white]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#AED6F1")),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Detalhes dos erros ──
    story.append(Paragraph("Detalhes dos Erros", section_style))
    story.append(Paragraph(
        f"Listagem completa das {len(errors)} ocorrencia(s) detectada(s):",
        body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    for i, err in enumerate(errors, start=1):
        level = err["level"]
        bg = LEVEL_BG.get(level, colors.HexColor("#FDECEA"))
        border_color = LEVEL_COLORS.get(level, colors.HexColor("#E74C3C"))

        header_data = [[
            Paragraph(f"<b>#{i}  [{level}]</b>", ParagraphStyle(
                f"EH{i}", fontSize=9, fontName="Helvetica-Bold",
                textColor=LEVEL_COLORS.get(level, colors.red),
            )),
            Paragraph(f"Linha {err['line']}  -  {err['timestamp']}", ParagraphStyle(
                f"EM{i}", fontSize=8, fontName="Helvetica",
                textColor=colors.HexColor("#5D6D7E"), alignment=TA_RIGHT,
            )),
        ]]
        header_table = Table(header_data, colWidths=[8.5 * cm, 8.5 * cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEABOVE", (0, 0), (-1, 0), 2, border_color),
        ]))

        msg_truncated = err["message"][:300] + ("..." if len(err["message"]) > 300 else "")
        msg_table = Table(
            [[Paragraph(msg_truncated, code_style)]],
            colWidths=[17 * cm],
        )
        msg_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDFEFE")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#AED6F1")),
        ]))

        story.append(KeepTogether([header_table, msg_table, Spacer(1, 0.15 * cm)]))

    # ── Rodapé ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#AED6F1"), spaceAfter=6))
    story.append(Paragraph(
        f"Relatorio gerado automaticamente pelo Monitor de Logs - {company} - "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        ParagraphStyle("Footer", fontSize=7.5, textColor=colors.HexColor("#AAB7B8"),
                       fontName="Helvetica", alignment=TA_CENTER),
    ))

    doc.build(story)
    return pdf_path


# ──────────────────────────────────────────────
#  Watchdog — monitoramento em tempo real
# ──────────────────────────────────────────────

class LogEventHandler(FileSystemEventHandler):
    def __init__(self, config: dict):
        self.config = config
        self._last_report = {}  # filepath -> timestamp do ultimo relatorio

    def _should_process(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in self.config["log_extensions"]

    def _handle(self, path: str):
        if not self._should_process(path):
            return

        # Cooldown — evita spam de PDFs
        now = time.time()
        last = self._last_report.get(path, 0)
        if now - last < self.config["cooldown_seconds"]:
            logger.debug(f"Cooldown ativo para {path}, ignorando.")
            return

        logger.info(f"Arquivo alterado: {path} — analisando erros...")
        errors = extract_errors(path, self.config["error_keywords"])

        if len(errors) >= self.config["min_errors_to_trigger"]:
            logger.info(f"  -> {len(errors)} erro(s) encontrado(s). Gerando PDF...")
            pdf = generate_pdf(
                log_file=path,
                errors=errors,
                output_dir=self.config["output_dir"],
                company=self.config["company_name"],
            )
            self._last_report[path] = now
            logger.info(f"  OK PDF gerado: {pdf}")
        else:
            logger.info(f"  -> Nenhum erro detectado (ou abaixo do minimo configurado).")

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

def main():
    log_dir = os.path.abspath(CONFIG["log_dir"])
    output_dir = os.path.abspath(CONFIG["output_dir"])

    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 55)
    logger.info("  Monitor de Logs - Portal Orquestrador RPA - DBSA")
    logger.info("=" * 55)
    logger.info(f"  Monitorando  : {log_dir}")
    logger.info(f"  Relatorios   : {output_dir}")
    logger.info(f"  Extensoes    : {CONFIG['log_extensions']}")
    logger.info(f"  Keywords     : {CONFIG['error_keywords']}")
    logger.info(f"  Cooldown     : {CONFIG['cooldown_seconds']}s entre relatorios")
    logger.info("=" * 55)
    logger.info("  Pressione Ctrl+C para encerrar.")
    logger.info("=" * 55)

    handler = LogEventHandler(CONFIG)
    observer = Observer()
    observer.schedule(handler, log_dir, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Encerrando monitor...")
        observer.stop()
    observer.join()
    logger.info("Monitor encerrado.")


if __name__ == "__main__":
    main()

"""Markdown and PDF renderers for itinerary export."""

from __future__ import annotations

from typing import Any

from fpdf import FPDF


def render_markdown(context: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# {context['trip_title']}",
        "",
        f"- **City:** {context['city'].title()}",
        f"- **Days:** {context['total_days']}",
        f"- **Generated:** {context['generated_at']}",
    ]
    if context.get("pace"):
        lines.append(f"- **Pace:** {context['pace']}")
    if context.get("interests"):
        lines.append(f"- **Interests:** {', '.join(context['interests'])}")
    lines.append("")

    for day in context["days"]:
        lines.append(f"## Day {day['day_number']}")
        if day.get("date"):
            lines.append(f"*{day['date']}*")
        if day.get("notes"):
            lines.append(f"> {day['notes']}")
        lines.append("")
        for block_name in ("morning", "afternoon", "evening"):
            activities = day["blocks"].get(block_name) or []
            if not activities:
                continue
            lines.append(f"### {block_name.title()}")
            for act in activities:
                lines.append(_format_activity_markdown(act))
            lines.append("")
        if day.get("travel_notes"):
            lines.append("**Estimated travel**")
            for note in day["travel_notes"]:
                lines.append(f"- {note}")
            lines.append("")

    if context.get("food_recommendations"):
        lines.append("## Food recommendations")
        for item in context["food_recommendations"]:
            lines.append(f"- {item}")
        lines.append("")

    if context.get("shopping_recommendations"):
        lines.append("## Shopping recommendations")
        for item in context["shopping_recommendations"]:
            lines.append(f"- {item}")
        lines.append("")

    if context.get("trip_notes"):
        lines.append("## Notes")
        lines.append(str(context["trip_notes"]))
        lines.append("")

    if context.get("sources"):
        lines.append("## Sources / References")
        for source in context["sources"]:
            lines.append(f"- {source}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _format_activity_markdown(act: dict[str, Any]) -> str:
    time_bits: list[str] = []
    if act.get("start") and act.get("end"):
        time_bits.append(f"{act['start']}–{act['end']}")
    elif act.get("start"):
        time_bits.append(str(act["start"]))
    duration = act.get("duration_minutes")
    if duration:
        time_bits.append(f"{duration} min")
    timing = f" ({', '.join(time_bits)})" if time_bits else ""
    note = f" — {act['notes']}" if act.get("notes") else ""
    return f"- **{act['title']}**{timing}{note}"


def render_pdf(context: dict[str, Any]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    width = pdf.epw
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(width, 10, _pdf_safe_text(context["trip_title"]))
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    pdf.set_text_color(60, 60, 60)
    meta = (
        f"{_pdf_safe_text(context['city'].title())} - {context['total_days']} days - "
        f"Generated {context['generated_at']}"
    )
    pdf.multi_cell(width, 6, meta)
    if context.get("pace"):
        pdf.multi_cell(width, 6, f"Pace: {context['pace']}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    for day in context["days"]:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_fill_color(240, 248, 255)
        pdf.cell(width, 10, f"Day {day['day_number']}", ln=True, fill=True)
        pdf.ln(2)
        for block_name in ("morning", "afternoon", "evening"):
            activities = day["blocks"].get(block_name) or []
            if not activities:
                continue
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(width, 7, block_name.title(), ln=True)
            pdf.set_font("Helvetica", size=10)
            for act in activities:
                line = f"  - {_format_activity_plain(act)}"
                pdf.multi_cell(width, 5, _pdf_safe_text(line))
            pdf.ln(1)
        if day.get("travel_notes"):
            pdf.set_font("Helvetica", "I", 10)
            pdf.multi_cell(width, 5, _pdf_safe_text("Travel: " + "; ".join(day["travel_notes"])))
        pdf.ln(3)

    _pdf_section_list(pdf, width, "Food recommendations", context.get("food_recommendations") or [])
    _pdf_section_list(pdf, width, "Shopping recommendations", context.get("shopping_recommendations") or [])
    if context.get("trip_notes"):
        _pdf_section_list(pdf, width, "Notes", [str(context["trip_notes"])])
    _pdf_section_list(pdf, width, "Sources / References", context.get("sources") or [])

    return bytes(pdf.output())


def _format_activity_plain(act: dict[str, Any]) -> str:
    parts = [act["title"]]
    if act.get("start"):
        parts.append(f"at {act['start']}")
    if act.get("duration_minutes"):
        parts.append(f"({act['duration_minutes']} min)")
    return " ".join(parts)


def _pdf_section_list(pdf: FPDF, width: float, title: str, items: list[str]) -> None:
    if not items:
        return
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(width, 8, title, ln=True)
    pdf.set_font("Helvetica", size=10)
    for item in items:
        pdf.multi_cell(width, 5, _pdf_safe_text(f"  - {item}"))
    pdf.ln(2)


def _pdf_safe_text(value: str) -> str:
    return (
        value.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u00b7", "-")
        .replace("\u2022", "-")
    )

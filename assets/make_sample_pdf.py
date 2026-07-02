"""Regenerate assets/sample.pdf — the fixed, known document the eval harness runs against.

Run this only if you want to rebuild the PDF: `python assets/make_sample_pdf.py`
(needs `reportlab`, which is already in the dev venv). The generated sample.pdf is
committed, so the normal eval flow never needs to run this.

Every fact below is deliberately unique so the eval can check that retrieval found the
*right* passage (see eval/dataset.py — each question's expected answer maps to one line here).
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


# The document's content: a fictional company handbook with 13 unique, checkable facts.
SECTIONS = [
    ("Northwind Analytics — Employee & Product Handbook (2026 Edition)", None),
    (
        "About the Company",
        "Northwind Analytics was founded in 2014 as a small data-consulting studio and has since grown "
        "into a product company. The business is headquartered in Bristol, United Kingdom, at an office "
        "located at 42 Harbour Road. The company's mission is to make demand forecasting accessible to "
        "mid-sized retailers who cannot afford large in-house data-science teams.",
    ),
    (
        "Leadership",
        "The current Chief Executive Officer is Dr. Amara Okonkwo, who joined the company in 2019 after "
        "leading analytics at a national logistics firm. The leadership team meets quarterly to review "
        "product strategy and company performance.",
    ),
    (
        "Our Flagship Product",
        "The flagship product is a demand-forecasting platform called TideCast. TideCast ingests a "
        "retailer's historical sales and produces weekly demand predictions, helping stores reduce both "
        "stockouts and overstock. It is sold as a subscription and is the company's primary source of "
        "revenue.",
    ),
    (
        "Time Off and Leave",
        "Full-time employees receive 28 days of paid annual leave each year, in addition to public "
        "holidays. Unused leave of up to five days may be carried over into the following year with "
        "manager approval.",
    ),
    (
        "Remote Work Policy",
        "Employees may work remotely up to three days per week. The company operates a hybrid model, and "
        "teams are expected to coordinate at least two shared in-office days for collaboration and "
        "onboarding of new joiners.",
    ),
    (
        "Health and Benefits",
        "The company health plan is provided through Meridian Health and covers all permanent employees "
        "from their first day. The plan includes dental cover and an employee assistance programme.",
    ),
    (
        "Expenses",
        "Business expenses under 75 pounds do not require pre-approval and can be claimed directly through "
        "the expenses portal. Any single expense above that threshold must be approved by a line manager "
        "before it is incurred. Each employee also has an annual training budget of 1,200 pounds for "
        "courses, books, and conferences.",
    ),
    (
        "Customer Support",
        "Customer support is available Monday to Friday, 9am to 6pm GMT. Support requests are answered by "
        "email and live chat, with a target first-response time of four business hours.",
    ),
    (
        "Data Security and Retention",
        "All company laptops must use full-disk encryption via SentinelLock, which is installed by the IT "
        "team during onboarding. Customer data is retained for 36 months after account closure, after "
        "which it is permanently deleted in line with the company's data-protection policy.",
    ),
]


def build_pdf(output_path: str) -> None:
    """Lay the SECTIONS out as a simple flowing PDF and write it to output_path."""
    styles = getSampleStyleSheet()
    story = []

    for i, (heading, body) in enumerate(SECTIONS):
        style = styles["Title"] if i == 0 else styles["Heading2"]
        story.append(Paragraph(heading, style))
        if body:
            story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 12))

    SimpleDocTemplate(output_path, pagesize=A4).build(story)


if __name__ == "__main__":
    out = Path(__file__).with_name("sample.pdf")
    build_pdf(str(out))
    print(f"Wrote {out}")

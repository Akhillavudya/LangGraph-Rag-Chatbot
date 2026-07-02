"""The fixed evaluation set: questions about assets/sample.pdf with their known answers.

Each DOC_QA item is a question whose answer lives in exactly one place in the sample PDF.
`expect` is a short, unique string that MUST appear in a correctly-retrieved chunk — that's
how the harness decides whether retrieval found the right passage (see eval/run_eval.py).

LATENCY_PROMPTS is a smaller set run through the full agent to time real end-to-end responses.
"""

# 13 retrieval questions — (question, the unique answer string that proves the right chunk was found).
DOC_QA = [
    {"query": "In what year was Northwind Analytics founded?", "expect": "2014"},
    {"query": "Which city is Northwind Analytics based in?", "expect": "Bristol"},
    {"query": "Who is the CEO of Northwind Analytics?", "expect": "Okonkwo"},
    {"query": "How many days of paid annual leave do full-time employees get?", "expect": "28 days"},
    {"query": "How many days per week can employees work remotely?", "expect": "three days"},
    {"query": "Which provider supplies the company health plan?", "expect": "Meridian"},
    {"query": "Below what amount do expenses not need pre-approval?", "expect": "75 pounds"},
    {"query": "What is the name of the company's flagship product?", "expect": "TideCast"},
    {"query": "How long is customer data retained after account closure?", "expect": "36 months"},
    {"query": "What are the customer support hours?", "expect": "9am to 6pm"},
    {"query": "What software is used for full-disk encryption on laptops?", "expect": "SentinelLock"},
    {"query": "What is the street address of the headquarters?", "expect": "42 Harbour Road"},
    {"query": "What is each employee's annual training budget?", "expect": "1,200"},
]

# A smaller mix run through the whole agent to measure latency (kept short to bound LLM cost).
LATENCY_PROMPTS = [
    {"prompt": "Who is the CEO of Northwind Analytics?", "kind": "rag"},
    {"prompt": "What is the name of the flagship product?", "kind": "rag"},
    {"prompt": "How many days of paid annual leave do full-time employees get?", "kind": "rag"},
    {"prompt": "What is 347 multiplied by 12?", "kind": "calculator"},
    {"prompt": "What is 15 percent of 240?", "kind": "calculator"},
    {"prompt": "In one sentence, what does Northwind Analytics do?", "kind": "general"},
]

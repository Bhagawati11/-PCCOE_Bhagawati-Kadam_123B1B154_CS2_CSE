# CS2 - Functional Safety HARA and Safety Requirement Management Assistant
Student: Bhagawati Kadam, PRN 123B1B154 (TechPulse FY-26, PCCOE Pune)

## Run (macOS/Linux)
1. python3 -m venv venv && source venv/bin/activate
2. pip install -r requirements.txt
3. ollama pull llama3.2:3b   (keep Ollama running)
4. cd Code && python run_eval.py          # evaluation, writes Evaluation_Results/
5. python run_eval.py --llm               # optional: also tests AI drafts (needs Ollama)
6. python -m streamlit run app.py         # app at http://localhost:8501

First run downloads the 90 MB embedding model (internet needed once). Everything else is local.

## What it does
- Hazard analysis: item function + guideword + situation -> similar approved library hazards (RAG) -> AI draft -> engineer sets S, E, C -> ASIL computed by a deterministic rule -> approve or reject.
- Safety goals, FSR and TSR: AI drafts, deterministic quality checker (rules REQ-1..REQ-5), engineer approval, ASIL inherited.
- Traceability: hazard -> goal -> FSR -> TSR matrix, gap detection (rule TRC-1), export CSV/JSON/Markdown.
- Citations: every AI answer is checked automatically for cited IDs that are not in the retrieved evidence.

## Data
All data is synthetic (Input_Data/). S/E/C ratings are illustrative and not ISO 26262 compliance claims.

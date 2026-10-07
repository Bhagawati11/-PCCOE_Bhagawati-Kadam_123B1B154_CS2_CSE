# Model, Prompt and Tool Configuration (CS2)
- LLM: Ollama, llama3.2:3b, local, temperature 0.1, no external API
- Embeddings: Sentence Transformers all-MiniLM-L6-v2 (local, normalised vectors)
- Vector store: FAISS IndexFlatIP, three indexes: item blocks (9), approved hazard library (14), rules (23)
- Chunking: one chunk per item block, per library hazard and per rule (each has a stable ID: ITM-n, HE-nnn, rule ID)
- Retrieval: top-3 library hazards, top-2 item blocks, top-3 rules for Q&A; all S/E/C/ASIL rules for rating suggestions
- Deterministic tools (Code/): asil.py (rule ASIL-1), reqcheck.py (REQ-1..REQ-5), traceability.py (TRC-1), SQLite log (db.py)
- System prompt: SYSTEM in Code/llm.py. Context is marked as untrusted data, model must cite IDs, must not decide the ASIL, and must reply 'Not found in supplied context.' when evidence is missing
- Task prompts: suggest_task, rating_task, sg_task, req_task, qa_task in Code/llm.py
- Citation check: llm.citation_check flags cited IDs that are not in the retrieved evidence

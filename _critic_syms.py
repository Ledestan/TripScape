import os, re

EH = [
 ("backend/api/recognition.py", ["recognize_sync","_validate","_attach_narrative_card"]),
 ("backend/api/narrative.py", ["get_card","add_card","deliver","def pick","my_journal","_gate","AddCardIn","DeliverIn","_landmark_or_404"]),
 ("backend/services/narrative_service.py", ["add_card_to_journal","journal_cards","deliver_fragment","pick_fragment","pick_fragment_by_id","fragment_payload","fragment_limit","_time_fragments","_rag_snippets","def _geo","build_narrative_card"]),
 ("backend/services/recognition_service.py", ["recognize_image","_build_result","RECOG_CONFIDENCE_THRESHOLD"]),
 ("backend/services/article_qa.py", ["class ArticleIndex","def search","K = 60","K=60","rrf","RRF"]),
 ("backend/apps/narrative/models.py", ["class NarrativeFragment","class FragmentPickup","class NarrativeCard","class JournalCard"]),
 ("backend/apps/journals/models.py", ["STATUS","class Journal"]),
 ("backend/api/journals.py", ["landmark_journals"]),
 ("backend/apps/core/auth.py", ["login_required"]),
 ("backend/config/settings/base.py", ["RECOG_CONFIDENCE_THRESHOLD","TRIPSCAPE2"]),
 ("backend/services/retrieval_engine.py", ["class ","FAISS"]),
]

for path, syms in EH:
    src = open(path, encoding="utf-8").read()
    print("==", path)
    for s in syms:
        print(("  FOUND " if s in src else "  MISSING ") + s)

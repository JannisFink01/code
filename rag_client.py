# rag_client.py
"""Wrapper um den produktiven RAG-Endpunkt (Qdrant Labor RAG with Reranking Moodle,
Open-WebUI-Pipeline v1.4.1). Ruft NICHT den Judge auf, sondern das System unter Test:
den RAG-Tutor, dessen Antworten anschliessend von DeepEval-Metriken bewertet werden.
Der Judge bleibt GWDGModel(JUDGE_MODEL) aus clients.py.

WICHTIGER HINWEIS (aus der Pipeline-Doku v1.4.1, Abschnitt 18 "Quellen-Ausgabe"):
Die Pipeline gibt KEIN separates JSON-Feld mit den abgerufenen Chunk-TEXTEN zurueck.
Quellen werden als Textblock an choices[0].message.content angehaengt und enthalten nur
Metadaten (Dateiname, Collection, Chunk-Nummer, Score) – nicht den eigentlichen Chunk-Text.
Fuer DeepEvals FaithfulnessMetric/ContextualPrecision/-Recall/-Relevancy wird aber der
tatsaechliche retrieval_context-TEXT benoetigt, nicht nur die Fundstelle. Mit dem aktuellen,
dokumentierten Response-Format ist retrieval_context daher NICHT direkt aus der Antwort
rekonstruierbar – siehe split_answer_and_sources() und die Hinweise am Ende der Datei.
"""
import re
import requests
import urllib3
from dataclasses import dataclass, field
from typing import Optional
from config import OPENWEBUI_BASE_URL, OPENWEBUI_API_KEY, RAG_MODEL, RAG_VERIFY_SSL

if not RAG_VERIFY_SSL:
    # -k im curl entspricht verify=False – nur fuer den Fall, dass Open WebUI selbst
    # ein Self-Signed-Zertifikat nutz Unterdrueckt
    # nur die Warnung, aendert nichts am eigentlichen Sicherheitskompromiss.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Format laut Doku Abschnitt 18:
# [1] filename.md | moodle_url=n/a | pages=n/a (collection=collection_vorlesung | page=n/a | chunk=11 | score=0.8521)
_SOURCE_LINE_RE = re.compile(
    r"^\[(?P<rank>\d+)\]\s*(?P<filename>[^|]+?)\s*\|\s*moodle_url=(?P<moodle_url>[^|]+?)\s*"
    r"\|\s*pages=(?P<pages>[^(]+?)\s*\(collection=(?P<collection>[^|]+?)\s*"
    r"\|\s*page=(?P<page>[^|]+?)\s*\|\s*chunk=(?P<chunk>[^|]+?)\s*\|\s*score=(?P<score>[\d.]+)\)\s*$"
)


@dataclass
class Citation:
    """Eine einzelne Quellenangabe aus dem 'Quellen:'-Block – Metadaten, kein Chunk-Text."""
    rank: str
    filename: str
    moodle_url: str
    pages: str
    collection: str
    page: str
    chunk: str
    score: float
    raw: str


@dataclass
class RAGAnswer:
    """Aufbereitete Antwort des RAG-Endpunkts.

    Attributes:
        text: Nur die eigentliche Tutor-Antwort, ohne angehängten Quellen-/Token-Block –
            das ist der korrekte Wert für `actual_output` in DeepEvals LLMTestCase.
        citations: Geparste Quellenangaben (Dateiname/Collection/Chunk/Score), falls die
            Pipeline einen Quellenblock angehängt hat. Enthält NICHT den Chunk-Text.
        retrieval_context: Bewusst None mit aktuellem, dokumentiertem Response-Format –
            siehe Modul-Docstring und Hinweis unten. Wird nur befüllt, falls ihr die
            Pipeline erweitert, um Roh-Chunks mitzuliefern (siehe unten).
        raw_response: Vollständige, ungeparste JSON-Antwort für Debugging.
    """
    text: str
    citations: list
    retrieval_context: Optional[list] = None
    raw_response: dict = field(default_factory=dict)


def split_answer_and_sources(content: str):
    """Trennt Tutor-Antwort von angehängtem 'Quellen:'- und optionalem 'Token:'-Block.

    Reihenfolge laut Doku Abschnitt 18: Antwort \n\n Quellen:\n... \n\n Token: ...
    Der Token-Block erscheint nur, wenn INCLUDE_TOKEN_USAGE_IN_RESPONSE=True ist
    (Server-Default: False) – wird hier trotzdem defensiv mit abgetrennt.

    Args:
        content: Rohtext aus choices[0].message.content.

    Returns:
        Tupel (answer_text, citations): `answer_text` ohne Quellen/Token-Suffix,
        `citations` als Liste von `Citation`-Objekten (leer, wenn kein Quellenblock
        vorhanden war, z. B. im LLM-only-Modus oder wenn keine Hits den
        RAG_SCORE_THRESHOLD überschritten haben).
    """
    text = content
    citations = []

    if "\nQuellen:" in text:
        answer_part, _, rest = text.partition("\nQuellen:")
        sources_part, _, _token_part = rest.partition("\nToken:")
        for line in sources_part.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            m = _SOURCE_LINE_RE.match(line)
            if m:
                gd = m.groupdict()
                citations.append(Citation(
                    rank=gd["rank"], filename=gd["filename"].strip(),
                    moodle_url=gd["moodle_url"].strip(), pages=gd["pages"].strip(),
                    collection=gd["collection"].strip(), page=gd["page"].strip(),
                    chunk=gd["chunk"].strip(), score=float(gd["score"]), raw=line,
                ))
            else:
                # Unerwartetes Format (z. B. Pipeline-Version geändert) – roh aufbewahren
                # statt stillschweigend zu verwerfen.
                citations.append(Citation("", "", "", "", "", "", "", 0.0, raw=line))
        text = answer_part
    elif "\nToken:" in text:
        text, _, _ = text.partition("\nToken:")

    return text.strip(), citations


class RAGPipelineClient:
    """Client für den 'Qdrant Labor RAG with Reranking Moodle'-Endpunkt (v1.4.1)."""

    def __init__(self, base_url=OPENWEBUI_BASE_URL, api_key=OPENWEBUI_API_KEY,
                 model=RAG_MODEL, verify_ssl=RAG_VERIFY_SSL, timeout=60):
        """Initialisiert den Client.

        Args:
            base_url: Basis-URL des Open-WebUI-Servers, z. B. "https://10.18.2.17:8080".
            api_key: Bearer-Token für die Authorization-Header.
            model: Pipeline-/Modellname, "qdrant_openwebui_rag_pipeline_rerank_moodle".
            verify_ssl: TLS-Zertifikat des Open-WebUI-Servers prüfen (False = curl -k).
            timeout: Timeout in Sekunden. Laut Doku hat der Server selbst 300s
                (REQUEST_TIMEOUT_SECONDS) für Embedding/Qdrant/LLM – bei aktivem
                Reranking zusätzlich RERANK_TIMEOUT_SECONDS (30s); der Client-Timeout
                hier sollte also nicht kleiner als der Server-Timeout gewählt werden.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def ask(
        self,
        question: str,
        system_prompt: str = "Du bist ein KI-Tutor im Kurs Elektrotechnik.",
        temperature: float = 0.2,
        top_p: float = 0.9,
        collections: str = "collection_labor, collection_vorlesung",
        retrieval: str = "dense",
        is_cross_encoder_rerank: bool = True,
        pipeline: str = "generalize",
        history: Optional[list] = None,
        moodle_meta: Optional[dict] = None,
        user: Optional[dict] = None,
    ) -> RAGAnswer:
        """Stellt eine Frage an den RAG-Tutor und gibt aufbereitete Antwort zurück.

        Args:
            question: Die aktuelle Nutzerfrage – wird als LETZTE `role="user"`-Message
                gesendet (laut Doku Abschnitt 3/8 ist NUR diese die "aktuelle Frage";
                ein evtl. mitgeschicktes top-level "question"-Feld ist reines
                Moodle-Metadatum und wird NICHT als Chat-Frage interpretiert).
            system_prompt: System-Message; überschreibt den Pipeline-eigenen SYSTEM_PROMPT.
            temperature, top_p: Sampling-Parameter.
            collections: Kommagetrennte Qdrant-Collections. Leerer String/Liste/None
                schaltet in den LLM-only-Modus (kein Retrieval, keine Quellen).
            retrieval: "dense" (produktiv), "sparse" oder "dense, sparse" (beide fallen
                mit den Server-Defaults auf Dense zurück, siehe Doku Abschnitt 9).
            is_cross_encoder_rerank: Bevorzugter Rerank-Parameter (Legacy: "isrerank").
            pipeline: Pipeline-Variante, reines Metadatum ohne Routing-Wirkung.
            history: Optionale Liste vorheriger {"role", "content"}-Turns, wird vor die
                aktuelle Frage gesetzt (für Multi-Turn-Nutzung dieses Endpunkts).
            moodle_meta: Optionales Dict mit Moodle-Feldern (section_id, module_id,
                question_id, question_type, ...). Nur gesetzte Felder werden mitgeschickt.
            user: Optionales User-Dict; Default: generischer Nutzer für automatisierte Läufe.

        Returns:
            RAGAnswer mit bereinigtem Antworttext, geparsten Quellen-Metadaten und der
            rohen JSON-Antwort. `retrieval_context` bleibt None (siehe Modul-Docstring).

        Raises:
            requests.HTTPError: Bei einem nicht-2xx-Status nach `raise_for_status()`.
        """
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": question})

        payload = {
            "stream": False,
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "collections": collections,
            "retrieval": retrieval,
            "is_cross_encoder_rerank": is_cross_encoder_rerank,
            "pipeline": pipeline,
            "user": user or {
                "name": "DeepEval-Runner",
                "id": "00000000-0000-0000-0000-000000000000",
                "email": "deepeval-runner@evaluierung.local",
                "role": "user",
            },
        }
        payload.update({k: v for k, v in (moodle_meta or {}).items() if v is not None})

        resp = requests.post(
            f"{self.base_url}/api/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        text, citations = split_answer_and_sources(raw_content)
        return RAGAnswer(text=text, citations=citations, retrieval_context=None, raw_response=data)
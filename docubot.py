"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re


STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "does", "for",
    "how", "i", "in", "is", "it", "mention", "of", "on", "or", "the", "there", "these",
    "this", "to", "what", "where", "which"
}

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split each document into smaller retrieval units.
        self.sections = self.load_sections(self.documents)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.sections)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    def _split_into_sections(self, text):
        """
        Splits a document into blank-line separated sections.
        """
        sections = []
        for block in re.split(r"\n\s*\n+", text):
            section = block.strip()
            if section:
                sections.append(section)
        return sections

    def load_sections(self, documents):
        """
        Converts whole documents into smaller labeled sections for retrieval.
        Returns a list of tuples: (section_label, text)
        """
        sections = []
        for filename, text in documents:
            for index, section in enumerate(self._split_into_sections(text), start=1):
                label = f"{filename}::section {index}"
                sections.append((label, section))
        return sections

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def _tokenize(self, text):
        """
        Converts text into simple lowercase tokens and removes common stopwords.
        """
        tokens = []
        for token in re.findall(r"[a-z0-9_]+", text.lower()):
            for part in token.split("_"):
                if not part:
                    continue

                normalized = part
                if normalized.endswith("ing") and len(normalized) > 5:
                    normalized = normalized[:-3]
                elif normalized.endswith("ed") and len(normalized) > 4:
                    normalized = normalized[:-2]
                    if normalized.endswith("at"):
                        normalized = normalized + "e"
                elif normalized.endswith("es") and len(normalized) > 4:
                    normalized = normalized[:-2]
                elif normalized.endswith("s") and len(normalized) > 3:
                    normalized = normalized[:-1]

                if normalized == "doc":
                    continue

                if normalized not in STOPWORDS:
                    tokens.append(normalized)
        return tokens

    def build_index(self, sections):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the sections
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md::section 2", "API_REFERENCE.md::section 1"],
            "database": ["DATABASE.md::section 3"]
        }

        Keep this simple: lowercase tokens and ignore punctuation if needed.
        """
        index = {}
        for section_label, text in sections:
            for token in self._tokenize(text):
                if token not in index:
                    index[token] = []

                if section_label not in index[token]:
                    index[token].append(section_label)

        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        text_token_counts = {}
        for token in self._tokenize(text):
            text_token_counts[token] = text_token_counts.get(token, 0) + 1

        score = 0
        for token in self._tokenize(query):
            score += text_token_counts.get(token, 0)

        return score

    def _minimum_evidence_score(self, query):
        """
        Returns the minimum score needed before we trust a retrieval result.
        Single-token queries are allowed to match once; longer queries need
        at least two overlapping tokens.
        """
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return 999

        if len(query_tokens) == 1:
            return 1

        return 2

    def retrieve(self, query, top_k=3):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (section_label, text) sorted by score descending.
        """
        if top_k <= 0:
            return []

        candidate_filenames = set()
        for token in self._tokenize(query):
            if token in self.index:
                candidate_filenames.update(self.index[token])

        if not candidate_filenames:
            return []

        sections_by_label = {section_label: text for section_label, text in self.sections}

        scored_results = []
        for section_label in candidate_filenames:
            text = sections_by_label.get(section_label, "")
            score = self.score_document(query, text)
            if score > 0:
                scored_results.append((score, section_label, text))

        scored_results.sort(key=lambda item: (-item[0], item[1]))

        if not scored_results:
            return []

        minimum_score = self._minimum_evidence_score(query)
        top_score = scored_results[0][0]
        if top_score < minimum_score:
            return []

        return [(section_label, text) for _, section_label, text in scored_results[:top_k]]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)

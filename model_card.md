# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

DocuBot is a small documentation assistant that answers questions about the files in the `docs/` folder. It compares three approaches: naive LLM generation over the full corpus, retrieval only, and retrieval plus Gemini generation. The goal is to show how grounding and retrieval quality affect answer reliability.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

DocuBot takes a user question, the documentation files in `docs/`, and an optional `GEMINI_API_KEY` from the environment. The CLI mode selection also controls whether it uses naive generation, retrieval only, or RAG.

**What outputs does DocuBot produce?**

It prints either a generated answer, raw retrieved snippets, or a refusal message when it lacks evidence. In RAG mode it also includes a short source note such as the file and section used.

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

The documents are split into blank-line separated sections, and each section becomes a retrieval unit. Each section is tokenized into lowercase terms, simple inflections are normalized, and an inverted index maps tokens to section labels like `AUTH.md::section 6`. Relevance is scored by token overlap between the query and each section, and the top scoring sections are returned.

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

I kept the implementation simple and dependency free, which makes it easy to reason about and debug. The tradeoff is that lexical matching can still confuse similar concepts, and blank-line chunking is only a rough proxy for meaning. It is much better than whole-document retrieval, but it still misses semantic relationships and can return the wrong nearby section.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

Naive LLM mode sends the full corpus question directly to Gemini with no retrieval step. Retrieval only mode does not call Gemini at all and prints the retrieved snippets. RAG mode retrieves a few sections first, then asks Gemini to answer using only those snippets.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

The RAG prompt tells Gemini to use only the provided snippets, avoid inventing functions or endpoints, refuse if the snippets are not enough, and reply exactly with `I do not know based on the docs I have.` when appropriate. It also asks the model to mention which files it relied on.

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Harmful. Confident but generic backend/JWT advice with no project-specific evidence. | Helpful. Returns the exact `AUTH.md` section that says `generate_access_token` is in `auth_utils.py`, but it still includes extra unrelated auth sections. | Helpful. Answers directly from `AUTH.md` and cites the file. | Good example of RAG being clearer than naive generation. |
| How do I connect to the database? | Harmful. Generic database setup advice, not the project docs. | Mixed. It returns `DATABASE.md`, but also drags in `SETUP.md` and the result is noisy. | Harmful. It refused even though the docs do describe database connection/configuration. | Shows that the retrieval threshold can be too strict. |
| Which endpoint returns all users? | Harmful. It guesses a generic `/users` endpoint and talks about pagination that is not in the docs. | Harmful. It surfaces `get_all_users()` from `DATABASE.md`, which is a helper function, not the API endpoint. | Mixed. It answered with `get_all_users()` from `DATABASE.md`, which is grounded in the docs but does not precisely answer the endpoint question. | Good example of retrieval confusing related concepts. |
| Is there any mention of payment processing in these docs? | Harmful. It confidently gives generic advice instead of checking the docs. | Helpful. Refuses with `I do not know based on these docs.` | Helpful. Also refuses. | Good negative test for the guardrail. |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

Naive LLM mode looks fluent even when it is almost entirely ungrounded, so its confidence is not useful evidence. Retrieval only is much more honest because it shows the source text, but it can be hard to interpret when the returned section is long or adjacent to the wrong concept. RAG is best when retrieval lands on the right section, because it turns the evidence into a short answer, but it still fails when retrieval chooses the wrong chunk or when the evidence threshold is too strict.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

1. Question: `How do I connect to the database?`  
	What happened: retrieval only returned relevant `DATABASE.md` text, but it also mixed in `SETUP.md`; RAG refused even though the docs do contain connection information.  
	What should have happened: retrieval should have picked the database connection section and RAG should have answered with that evidence.

2. Question: `Which endpoint returns all users?`  
	What happened: retrieval only and RAG both preferred `get_all_users()` from `DATABASE.md` instead of the `/api/users` route in `API_REFERENCE.md`.  
	What should have happened: the system should have prioritized the endpoint section and distinguished it from the database helper function.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

It should refuse when the docs do not mention the topic at all, such as payment processing. It should also refuse when retrieval finds only weakly related evidence and the system cannot support a specific answer without guessing.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

I split documents into smaller blank-line sections, limited retrieval to the top scoring sections, and added a minimum evidence threshold before returning results. I also kept an explicit refusal path in both retrieval-only and RAG mode so unsupported questions do not get answered with a guess.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. Lexical scoring can confuse related but different concepts, such as API endpoints versus helper functions.
2. The chunking strategy is simple and can still return noisy or adjacent sections.
3. RAG is only as good as retrieval, so a weak chunk choice can produce a refusal or a partial answer.

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. Add heading-aware chunking so sections align better with document structure.
2. Improve ranking with phrase matching or query expansion so endpoint questions beat nearby helper text.
3. Add shorter snippets or highlighted evidence so retrieval output is easier to inspect.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

It could mislead a developer into calling the wrong endpoint, using the wrong auth flow, or trusting configuration advice that is not actually in the docs. The bigger risk is over trusting a fluent answer when the model is really guessing.

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- Treat naive LLM answers as hypotheses, not facts.
- Check the source snippets before acting on a retrieval or RAG answer.
- Refuse or verify any answer that affects authentication, database access, or other sensitive behavior.

---

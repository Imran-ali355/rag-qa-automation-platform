import requests
from app import TXT_COLLECTION, DOCS_DIR, CHAT_MODEL, OLLAMA_CHAT_URL, retrieve_relevant_chunks


def run_terminal_chat():
    print("Simple Terminal RAG Chatbot ready! Type 'exit' or 'quit' to stop.\n")

    while True:
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if TXT_COLLECTION is None or TXT_COLLECTION.count() == 0:
            print(f"\nBot: No .txt files found in '{DOCS_DIR}/'.\n")
            continue

        context_chunks = retrieve_relevant_chunks(question, top_k=4)
        context_text = "\n\n---\n\n".join(context_chunks)

        prompt = (
            "Answer the question strictly based on the provided context from local TXT files. "
            "If the answer is not found in the context, clearly state that this information is not in the files.\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"QUESTION:\n{question}"
        )

        try:
            resp = requests.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            answer = resp.json().get("message", {}).get("content", "").strip()
            print(f"\nBot: {answer}\n")
        except Exception as exc:
            print(f"\nBot error: {exc}\n")


if __name__ == "__main__":
    run_terminal_chat()
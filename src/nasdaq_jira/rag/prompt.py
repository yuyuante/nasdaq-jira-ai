"""Prompt construction for retrieved Jira context."""

from .models import SearchResult


class PromptBuilder:
    def build(self, query: str, results: list[SearchResult]) -> str:
        unique: dict[str, SearchResult] = {
            result.chunk_id: result for result in results
        }
        context = "\n\n".join(
            f"[{item.issue_key} | updated={item.updated_at}] {item.text}"
            for item in unique.values()
        )
        instructions = (
            "Return executive_summary, technical_summary, action_items, "
            "related_issues, confidence (0-1), and sources. "
            "Cite issue keys and updated times. Never invent facts."
        )
        return f"Question: {query}\n\nContext:\n{context}\n\n{instructions}"

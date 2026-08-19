from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.memory import memory_service
from app.services.sandbox import sandbox_manager
from app.services.skill_loader import skill_registry


class AgentRuntime:
    """Builds the persistent context injected into a future LLM/DeepAgents runtime."""

    def build_context(self, db: Session, project_id: str, agent_key: str, query: str | None = None) -> dict:
        memories = memory_service.retrieve(
            db, project_id=project_id, agent_key=agent_key, query=query,
            limit=20, touch=True,
        )
        skills = skill_registry.list(agent_key=agent_key)
        memory_prompt = memory_service.build_prompt(memories)
        skill_prompt = self.build_skill_prompt(skills)
        return {
            "memories": memories,
            "skills": skills,
            "memory_prompt": memory_prompt,
            "skill_prompt": skill_prompt,
            "sandbox": sandbox_manager.status(),
        }

    @staticmethod
    def build_skill_prompt(skills) -> str:
        if not skills:
            return "No skills are loaded for this agent type."
        sections = ["## Loaded skills"]
        for skill in skills:
            sections.append(f"### {skill.display_name} ({skill.name}@{skill.version})\n{skill.instructions}")
        return "\n\n".join(sections)


agent_runtime = AgentRuntime()

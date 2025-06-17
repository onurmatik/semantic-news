from typing import List
from pydantic import BaseModel
from agents import Agent, Runner

class OpinionSuggestionList(BaseModel):
    """List of short opinions."""
    opinions: List[str]

class OpinionSuggestionAgent:
    name = "Opinion Suggestion Agent"
    instructions = (
        "You are a commentator providing short opinions on the given topic recap. "
        "Return 2-3 brief opinions."
    )

    async def run(self, recap: str, lang: str = 'tr'):
        agent = Agent(
            name=self.name,
            instructions=f"{self.instructions} Respond in {'Turkish' if lang == 'tr' else 'English'}.",
            output_type=OpinionSuggestionList,
        )
        result = await Runner.run(agent, recap)
        return result.final_output

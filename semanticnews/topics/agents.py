from typing import List, Optional, Literal
from pydantic import BaseModel
from agents import Agent, Runner, WebSearchTool
from openai.types.responses.web_search_tool_param import UserLocation


_TOPIC_GUIDELINES = """
### Topic Guidelines:

1. **Significance**: 
   Topics should have **significant presence or impact**, particularly in the Turkish context. 

2. **Focus**: 
   Topics should not be too broad or too specific.
   - ❌ Doğurganlık
   - ❌ Türkiye'de doğurganlık oranının 1.51'e düşmesi
   - ✅ Türkiye'de doğurganlık oranının düşmesi
   Allow topics to be broad if they refer to an event at a specific date.
   - ✅ 6 Şubat depremi
   - ✅ Saraçhane eylemleri - Mart 2025

3. **Neutrality**: 
   Each topic should be a **short and neutral description of the main event or situation** — no additional details, opinions, or consequences.  
   - ❌ Ekrem İmamoğlu'nun gözaltına alınması ve kamuoyu tepkileri
   - ❌ İstanbul Büyükşehir Belediye Başkanı Ekrem İmamoğlu'nun gözaltına alınması
   - ✅ Ekrem İmamoğlu'nun gözaltına alınması

4. **Grammar**:
    Prefer nominalized passive form instead of a finite passive clause where applicable.
    - ❌ Ekrem İmamoğlu gözaltına alındı
    - ✅ Ekrem İmamoğlu'nun gözaltına alınması
"""


class TopicSchema(BaseModel):
    """
    List of news agenda topics.

    Attributes:
        name (str): The name of the news agenda topic.
        categories (List[str]): The list of categories that the news agenda topic belongs to. Avoid overly generic categories like "Gündem", "Haber", etc.
        significance (str): 'low', 'normal' or 'high'; the importance of the event covered in the article, particularly in the Turkish context
    """
    name: str
    categories: List[str]
    significance: str


class TopicListSchema(BaseModel):
    """
    List of news agenda topics.

    Attributes:
        topics (List[TopicSchema]): A list of topics.
    """
    topics: Optional[List[TopicSchema]]


class TopicEvaluationResultSchema(BaseModel):
    """
    Represents the evaluation result of a news topic according to predefined editorial guidelines.

    Attributes:
        status (Literal["OK", "revision", "reject"]):
            The outcome of the evaluation.
            - "OK" if the original topic adheres to all guidelines.
            - "revision" if the topic needs revision.
            - "reject" if the topic violates general moderation policies (e.g., abusive, discriminatory, or nonsensical content).
        suggested_topic (Optional[str]): The revised version of the topic, provided only when `status` is "revision".
        reason (Optional[str]): A concise explanation of why the topic was not accepted. Provided only when status is "revision" or "reject".
    """
    status: Literal["OK", "revision", "reject"]
    suggested_topic: Optional[str] = None
    reason: Optional[str] = None


class TopicEvaluationAgent:
    name = "Topic Evaluation Agent"
    instructions = (
        "You are a news editor specialized in Turkish context. Your task is to evaluate the given topic. "
        "Return the topic as is if it is OK. Otherwise return 'revision' with a very short single-sentence explanation in the SAME LANGUAGE as the provided topic. "
        "If it is possible to correct the issues with minor changes, provide a revised version of the topic. "
    )
    guidelines = _TOPIC_GUIDELINES

    async def run(self, topic, lang='tr'):
        instructions = (
            f"{self.instructions}\n"
            f"Respond in {lang=='tr' and 'Turkish' or 'English'}.\n\n"
            f"{self.guidelines}"
        )

        agent = Agent(
            name=self.name,
            instructions=instructions,
            output_type=TopicEvaluationResultSchema,
        )

        result = await Runner.run(agent, topic)

        return result.final_output


class TopicCreationAgent:
    name = "Topic Creation Agent"
    instructions = (
        "You are a news editor, tasked to parse the given topic string."
    )

    async def run(self, topic, lang='tr'):
        instructions = (
            f"{self.instructions}\n"
            f"Respond in {lang=='tr' and 'Turkish' or 'English'}."
        )

        agent = Agent(
            name=self.name,
            instructions=instructions,
            output_type=TopicSchema,
        )

        result = await Runner.run(agent, topic)

        return result.final_output


# Suggestions

class SuggestedTopicSchema(BaseModel):
    """
    A topic for the article.

    Attributes:
        topic (str): A name for the topic.
    """
    topic: str


class SuggestedTopicListSchema(BaseModel):
    """
    List of news agenda topics.

    Attributes:
        topics (List[str]): A list of topics.
    """
    topics: List[str]


class TopicSuggestionAgent:
    name = "Topic Suggestion Agent"
    instructions = (
        "You are a news editor. Based on the given article, suggest a news topic relevant to the Turkish context and agenda. "
        "Avoid too broad or too specific topics."
    )
    guidelines = _TOPIC_GUIDELINES

    async def run(self, article, lang='tr'):
        instructions = (
            f"{self.instructions}\n"
            f"Respond in {'Turkish' if lang == 'tr' else 'English'}.\n\n"
            f"{self.guidelines}"
        )
        agent = Agent(
            name=self.name,
            instructions=instructions,
            output_type=SuggestedTopicSchema,
            tools=[
                WebSearchTool(
                    user_location=UserLocation(country='TR', type='approximate'),
                    search_context_size='low',  # low, medium, high
                ),
            ],
        )
        result = await Runner.run(agent, article)

        return result.final_output


class TopicListSuggestionAgent:
    name = "Topic List Suggestion Agent"
    instructions = (
        "You are a news editor. Based on the given search term, suggest 3-5 news topics relevant to the Turkish context and agenda. "
        "Avoid too broad or too specific topics."
    )
    guidelines = _TOPIC_GUIDELINES

    async def run(self, search_term, lang='tr'):
        instructions = (
            f"{self.instructions}\n" 
            f"Respond in {'Turkish' if lang == 'tr' else 'English'}.\n\n"
            f"{self.guidelines}"
        )
        agent = Agent(
            name=self.name,
            instructions=instructions,
            output_type=SuggestedTopicListSchema,
            tools=[
                WebSearchTool(
                    user_location=UserLocation(country='TR', type='approximate'),
                    search_context_size='low',  # low, medium, high
                ),
            ],
        )
        result = await Runner.run(agent, search_term)

        return result.final_output


# Entity graph

class TopicEntity(BaseModel):
    """
    Entities mentioned in the news.

    Attributes:
        name (str): The name of the singular entity.
        type (str): The type of entity (e.g., person, place, organization, etc.).
    """
    name: str
    type: str


class TopicEntityRelation(BaseModel):
    """
    Relations between entities, representing edges in the entity relations graph.

    Attributes:
        type (str): The type of relationship between entities (e.g., been_to, graduated_from, involved_in, works_for, etc.).
        source (str): The name of the source entity.
        target (str): The name of the target entity.
    """
    type: str
    source: str
    target: str


class TopicEntityGraph(BaseModel):
    """
    The graph that contains nodes (entities) and edges (relations) derived from news related to a topic.

    Attributes:
        entities (List[TopicEntity]): A list of unique entities mentioned in the news.
        relations (List[TopicEntityRelation]): A list of relations between the entities.
    """
    entities: List[TopicEntity]
    relations: List[TopicEntityRelation]


class TopicEntityRelationsAgent:
    name = "Topic Entity Relations Agent"
    instructions = (
        "You are a news editor specialized in Turkish agenda. Your task is to analyze the given news "
        "and extract entities mentioned and their relationships in an entity - relations graph format."
    )

    async def run(self, news):
        agent = Agent(
            name=self.name,
            instructions=self.instructions,
            output_type=TopicEntityGraph,
        )

        result = await Runner.run(agent, news)

        return result.final_output


# Recap

class TopicRecapSchema(BaseModel):
    """
    Relations between entities, representing edges in the entity relations graph.

    Attributes:
        recap_tr (str): Recap of the topic in Turkish.
        recap_en (str): Recap of the topic in English.
    """
    recap_tr: str
    recap_en: str


class TopicRecapAgent:
    name = "Topic Recap Agent"
    instructions = (
        "You are a news editor. "
        "Given the relevant content on the topic, generate a 1 paragraph concise, coherent recap in Markdown. "
        "Summarize the essential narrative and main points. Keep it brief, engaging and easy to scan. "
        "Maintain a neutral tone, even if the content is biased. Respond in Turkish and in English. "
        "Highlight the key entities by making them bold. "
    )

    async def run(self, news, websearch: bool = False):
        kwargs = dict(
            name=self.name,
            instructions=self.instructions,
            output_type=TopicRecapSchema,
        )

        if websearch:
            kwargs["tools"] = [
                WebSearchTool(
                    user_location=UserLocation(country="TR", type="approximate"),
                    search_context_size="low",
                )
            ]

        agent = Agent(**kwargs)

        result = await Runner.run(agent, news)

        return result.final_output



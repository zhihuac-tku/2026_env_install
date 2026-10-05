 # py code beginning

"""LilyLab Ecotourism Marketing Agent."""

from dataclasses import dataclass
from typing import Any

from pydantic_ai import (
    Agent,
    RunContext,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)

from lilylab_ecotourism.product_search import (
    search_ecotourism_products,
)

from lilylab_ecotourism.weather_context import (
    get_weather_context,
)


@dataclass
class EcotourismMarketingDeps:
    """
    Runtime dependencies and execution trace
    for Marketing Agent tools.
    """

    engine: Any

    product_search_called: bool = False
    product_search_count: int = 0
    product_search_limit: int = 0

@dataclass
class EcotourismTravelBriefDeps:
    """
    Runtime dependencies and execution trace
    for Travel Brief Agent tools.
    """

    weather_cfg: dict[str, Any]
    destination: dict[str, Any]
    travel_time: dict[str, Any]

    weather_tool_called: bool = False
    forecast_available: bool = False
    weather_observation_count: int = 0
    weather_context: dict[str, Any] | None = None

def create_ecotourism_marketing_agent(
    llm_cfg: dict[str, Any],
) -> Agent:
    """
    Create the general ecotourism marketing agent.

    Used for marketing tasks that do not require
    database tools.
    """

    model = build_agent_model(
        llm_cfg
    )

    return Agent(
        model=model,
        instructions=(
            "You are an ecotourism marketing agent. "
            "Analyze customer travel needs and produce "
            "grounded marketing recommendations. "
            "Do not invent products, prices, locations, "
            "URLs, or other product facts."
        ),
    )

def create_ecotourism_travel_brief_agent(
    llm_cfg: dict[str, Any],
) -> Agent:
    """
    Create the Travel Brief Agent.

    The Agent may use CWA weather evidence
    when weather information is useful for
    preparing the travel brief.
    """

    model = build_agent_model(
        llm_cfg
    )

    agent = Agent(
        model=model,
        deps_type=EcotourismTravelBriefDeps,
        instructions=(
            "You are an ecotourism travel "
            "preparation agent. "
            "Analyze the travel requirements "
            "and produce practical preparation "
            "advice. "
            "When weather conditions may affect "
            "travel preparation, use the "
            "weather tool to obtain official "
            "weather evidence. "
            "Do not invent weather conditions. "
            "If weather evidence is unavailable, "
            "continue the travel preparation "
            "analysis without inventing weather "
            "facts."
        ),
    )

    @agent.tool
    def get_weather(
        ctx: RunContext[
            EcotourismTravelBriefDeps
        ],
    ) -> dict[str, Any]:
        """
        Retrieve official CWA weather evidence
        for the destination and travel period.
        """

        ctx.deps.weather_tool_called = True

        weather_context = (
            get_weather_context(
                weather_cfg=(
                    ctx.deps.weather_cfg
                ),
                destination=(
                    ctx.deps.destination
                ),
                start_date=str(
                    ctx.deps.travel_time.get(
                        "start_date",
                        "",
                    )
                ).strip(),
                end_date=str(
                    ctx.deps.travel_time.get(
                        "end_date",
                        "",
                    )
                ).strip(),
            )
        )

        ctx.deps.weather_context = (
            weather_context
        )

        forecast_available = bool(
            weather_context.get(
                "forecast_available",
                False,
            )
        )

        ctx.deps.forecast_available = (
            forecast_available
        )

        records = (
            weather_context.get(
                "records",
                {},
            )
        )

        if isinstance(
            records,
            dict,
        ):
            ctx.deps.weather_observation_count = (
                len(records)
            )

        elif isinstance(
            records,
            list,
        ):
            ctx.deps.weather_observation_count = (
                len(records)
            )

        else:
            ctx.deps.weather_observation_count = 0

        return weather_context

    return agent

def create_ecotourism_product_agent(
    llm_cfg: dict[str, Any],
) -> Agent:
    """
    Create the ReAct-capable ecotourism product
    recommendation agent.
    """

    model = build_agent_model(
        llm_cfg
    )

    agent = Agent(
        model=model,
        deps_type=EcotourismMarketingDeps,
        instructions=(
            "You are an ecotourism marketing agent. "
            "You recommend real ecotourism products "
            "based on customer travel requirements. "
            "Use the available product search tool "
            "when product evidence is required. "
            "Base product recommendations only on "
            "products returned by the tool. "
            "Do not invent product IDs, names, prices, "
            "locations, URLs, or other product facts."
        ),
    )

    @agent.tool
    def search_products(
        ctx: RunContext[
            EcotourismMarketingDeps
        ],
        candidate_limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search active ecotourism products from the
        product database.

        Use this tool before making product
        recommendations.
        """

        candidate_df = (
            search_ecotourism_products(
                engine=ctx.deps.engine,
                candidate_limit=(
                    candidate_limit
                ),
            )
        )

        ctx.deps.product_search_called = True

        ctx.deps.product_search_limit = int(
            candidate_limit
        )

        ctx.deps.product_search_count = len(
            candidate_df
        )

        if candidate_df.empty:
            return []

        candidate_df = (
            candidate_df.where(
                candidate_df.notna(),
                None,
            )
        )

        return candidate_df.to_dict(
            orient="records"
        )

    return agent


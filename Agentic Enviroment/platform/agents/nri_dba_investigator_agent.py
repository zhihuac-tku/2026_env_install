 # py code beginning

"""Pydantic AI ReAct-style DBA Investigator.

The Agent decides which read-only evidence tools to call. Database engines are
supplied through dependencies and are never exposed as model arguments.
"""

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext, UsageLimits

from models.nri_dba_investigator_models import (
    DBAInvestigationResult,
)
from nri_dba.evidence import (
    analyze_relationship_candidates,
    analyze_relationship_column_usage,
    inspect_columns,
    inspect_columns_by_names,
    inspect_foreign_keys,
    inspect_primary_keys,
    inspect_primary_keys_by_column_names,
    inspect_table_evidence,
    summarize_relationship_impact,
)

from nri_ai_core.ai_runtime import build_agent_model


@dataclass
class DBAInvestigatorDeps:
    target_engine: Any
    dictionary_engine: Any
    source_db: str
    schema_name: str
    table_name: str


INSTRUCTIONS = """
You are the NRI DBA Investigator.

Investigate database design using only the supplied read-only tools.

WORKFLOW
1. For a normal table review, call table_evidence first.
2. Examine that baseline evidence before deciding whether any drill-down is needed.
3. Prefer the final result immediately when the baseline is sufficient.
4. Call relationship_candidates only when a specific relationship question remains.
5. Call relationship_column_usage only for a small, explicit set of selected
   columns justified by prior evidence.
6. Do not repeat a tool call unless genuinely new evidence requires it.
7. Stop when enough evidence exists and produce the final structured result.

TOOL ECONOMY
- table_evidence: LOW COST. Use first.
- relationship_candidates: MEDIUM COST. It searches only column names present
  in the target table; use it only when relationship evidence is relevant.
- relationship_column_usage: MEDIUM/HIGH COST. Supply only the smallest useful
  selected_columns list. Never use it as a request for broad database discovery.
- Do not mechanically call every tool.

EVIDENCE RULES
- Never invent tables, columns, keys, indexes, constraints, dictionary content,
  or relationships.
- Distinguish physical database evidence from semantic dictionary evidence and
  inferred relationship candidates.
- A candidate relationship is not a physical foreign key.
- Missing dictionary information is not proof that business semantics do not
  exist.
- Do not perform or request database-changing operations.
- Recommendations are advisory and database design changes require human review.

FINAL OUTPUT
Return exactly the structured result requested by the output schema:
- summary: string
- findings: list
- unresolved_questions: list

Each finding must contain:
- category
- severity
- finding
- evidence
- recommendation
- requires_human_review

Do not add bookkeeping about tool calls to the final result.
Do not add fields outside the output schema.
"""



def create_dba_investigator_agent(model) -> Agent:
    agent = Agent(
        model=model,
        deps_type=DBAInvestigatorDeps,
        output_type=DBAInvestigationResult,
        instructions=INSTRUCTIONS,
        retries=3,
    )

    @agent.tool
    def table_evidence(ctx: RunContext[DBAInvestigatorDeps]):
        """Collect baseline physical and semantic evidence for the target table.

        Use this first for a normal table-design investigation. It returns
        columns, PKs, FKs, indexes, UNIQUE constraints, table dictionary, and
        column dictionary in one deterministic read-only call.
        """
        return inspect_table_evidence(
            ctx.deps.target_engine,
            ctx.deps.dictionary_engine,
            source_db=ctx.deps.source_db,
            schema_name=ctx.deps.schema_name,
            table_name=ctx.deps.table_name,
        )

    @agent.tool
    def relationship_candidates(
        ctx: RunContext[DBAInvestigatorDeps],
    ):
        """Drill down into inferred relationship candidates when needed.

        Candidate relationships are analytical evidence only and must never be
        described as physical foreign-key constraints.
        """
        target_columns = inspect_columns(
            ctx.deps.target_engine,
            schema_name=ctx.deps.schema_name,
            table_name=ctx.deps.table_name,
        )
        target_column_names = [
            str(row.get("column_name", "")).strip()
            for row in target_columns
            if str(row.get("column_name", "")).strip()
        ]

        relevant_columns = inspect_columns_by_names(
            ctx.deps.target_engine,
            column_names=target_column_names,
        )
        relevant_pks = inspect_primary_keys_by_column_names(
            ctx.deps.target_engine,
            column_names=target_column_names,
        )
        target_fks = inspect_foreign_keys(
            ctx.deps.target_engine,
            schema_name=ctx.deps.schema_name,
            table_name=ctx.deps.table_name,
        )

        return analyze_relationship_candidates(
            all_columns=relevant_columns,
            primary_keys=relevant_pks,
            foreign_keys=target_fks,
            schema_name=ctx.deps.schema_name,
            table_name=ctx.deps.table_name,
        )

    @agent.tool
    def relationship_column_usage(
        ctx: RunContext[DBAInvestigatorDeps],
        selected_columns: list[dict[str, Any]],
    ):
        """Drill down into enterprise usage of selected relationship columns."""
        selected_column_names = [
            str(row.get("column_name", "")).strip()
            for row in selected_columns
            if str(row.get("column_name", "")).strip()
        ]

        relevant_columns = inspect_columns_by_names(
            ctx.deps.target_engine,
            column_names=selected_column_names,
        )

        return analyze_relationship_column_usage(
            all_columns=relevant_columns,
            selected_columns=selected_columns,
        )

    return agent


def run_dba_investigation(
    *,
    llm_cfg: dict,
    target_engine: Any,
    dictionary_engine: Any,
    source_db: str,
    schema_name: str,
    table_name: str,
    user_instruction: str,
):
    model = build_agent_model(llm_cfg)
    agent = create_dba_investigator_agent(model)

    deps = DBAInvestigatorDeps(
        target_engine=target_engine,
        dictionary_engine=dictionary_engine,
        source_db=source_db,
        schema_name=schema_name,
        table_name=table_name,
    )

    prompt = (
        f"Investigate {source_db}.{schema_name}.{table_name}.\n"
        f"User request: {user_instruction}"
    )

    # --------------------------------------------------------
    # TOKEN BUDGET
    # --------------------------------------------------------
    # num_predict comes from the shared NRI AI Runtime UI.
    # It controls the maximum output of one model request.
    #
    # A tool-using Agent may make several model requests, so
    # its whole-run token budget must be larger than the
    # per-request output limit.
    max_output_tokens = int(
        llm_cfg.get(
            "num_predict",
            5000,
        )
        or 5000
    )

    agent_total_tokens = max(
        max_output_tokens * 6,
        20_000,
    )

    model_settings = {
        "temperature": float(
            llm_cfg.get(
                "temperature",
                0.2,
            )
        ),
        "max_tokens": max_output_tokens,
    }

    result = agent.run_sync(
        prompt,
        deps=deps,
        model_settings=model_settings,
        usage_limits=UsageLimits(
            request_limit=5,
            tool_calls_limit=8,
            total_tokens_limit=agent_total_tokens,
        ),
    )
    return result.output



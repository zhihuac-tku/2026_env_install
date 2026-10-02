 # py code beginning

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent

from models.nri_dba_ai_data_dictionary_models import (
    AIDataDictionaryReport,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)


AI_DATA_DICTIONARY_AGENT_INSTRUCTIONS = """
你是 NRI Taiwan 的資深 PostgreSQL DBA、企業資料架構師、
資料治理顧問、資料字典專家與 AI Data Steward。

根據 supplied PostgreSQL metadata、既有 Table Dictionary 與
Column Dictionary，建立完整、可稽核且供 DBA 人工審查的
AI Data Dictionary。

規則：
- 只能使用 supplied context。
- 不可發明不存在的 database、schema、table 或 physical column。
- 每個 physical column 必須在 column_dictionary 中剛好出現一次。
- 不可修改 physical column_name。
- 既有且合理的人工資料字典內容應優先保留，只補充缺漏。
- verified dictionary 內容應優先保留。
- 沒有實際資料值時，不可發明 allowed_values 或 example_values。
- 無法確認的內容使用空字串，並在 review_note 說明。
- 候選業務意義不可描述為已確認的業務事實。
- 根據 PK、FK、Index、欄位名稱及既有 dictionary 判斷 data role。
- 可提出 BI、Analytics、RAG 與 LLM 使用建議，但必須由 evidence 支持。
- AI 產生內容一律為 draft；verified 必須為 false。
- 全文使用繁體中文。
- section 只能是 text 或 table。
- table_id 只能是 ai_table_profile、ai_column_dictionary 或 design_review。
- table section 不可自行建立 rows、columns 或 data。
"""


def create_ai_data_dictionary_agent(
    model,
) -> Agent:
    return Agent(
        model=model,
        output_type=AIDataDictionaryReport,
        instructions=(
            AI_DATA_DICTIONARY_AGENT_INSTRUCTIONS
        ),
    )


def _agent_model_settings(
    llm_cfg: dict[str, Any],
) -> dict:
    settings = {
        "temperature": float(
            llm_cfg.get(
                "temperature",
                0.0,
            )
            or 0.0
        ),
    }

    num_predict = int(
        llm_cfg.get(
            "num_predict",
            0,
        )
        or 0
    )

    if num_predict > 0:
        settings[
            "max_tokens"
        ] = num_predict

    return settings


def run_ai_data_dictionary_agent(
    *,
    report_context: dict,
    user_instruction: str,
    llm_cfg: dict,
) -> dict:
    """
    Execute the AI Data Dictionary Agent.

    Physical metadata and existing dictionary information are
    supplied by the application as source context.

    Agent/model execution remains inside the Agent layer.
    """

    if (
        not llm_cfg
        or not llm_cfg.get(
            "enabled"
        )
    ):
        raise RuntimeError(
            "LLM backend is disabled."
        )

    model = build_agent_model(
        llm_cfg
    )

    agent = (
        create_ai_data_dictionary_agent(
            model
        )
    )

    physical_column_names = [
        str(
            row.get(
                "column_name",
                "",
            )
        ).strip()
        for row in report_context.get(
            "physical_columns",
            [],
        )
        if str(
            row.get(
                "column_name",
                "",
            )
        ).strip()
    ]

    prompt = (
        "請根據以下 PostgreSQL Table Context "
        "建立完整的 AI Data Dictionary。\n"
        "column_dictionary 必須完整涵蓋以下 "
        "physical columns，"
        "每個欄位剛好一次，不可增加、刪除或改名：\n"
        + json.dumps(
            physical_column_names,
            ensure_ascii=False,
        )
        + "\n\nUSER INSTRUCTION:\n"
        + str(
            user_instruction
            or ""
        ).strip()
        + "\n\nPOSTGRESQL TABLE CONTEXT:\n"
        + json.dumps(
            report_context,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    result = agent.run_sync(
        prompt,
        model_settings=(
            _agent_model_settings(
                llm_cfg
            )
        ),
    )

    return (
        result.output.model_dump()
    )



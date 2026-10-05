 # py code beginning

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent

from models.nri_dba_business_consistency_models import (
    BusinessConsistencyReport,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)


BUSINESS_CONSISTENCY_AGENT_INSTRUCTIONS = """
你是 NRI Taiwan 的資深 PostgreSQL DBA、企業資料架構師與
業務資料模型顧問，同時擔任 Business Consistency Review
報告的 Chief Editor。

任務：
根據應用程式提供的 Business Consistency Context，判斷同一欄位
在不同資料表中的使用是否具有合理且一致的業務意義，並產生正式、
可稽核且以事實為基礎的審查報告。

必須：
- 使用 table_business_name 判斷資料表業務情境。
- 使用 column_business_name、欄位描述、資料型別、Nullability、
  Primary Key 與 Foreign Key 角色判斷語意一致性。
- 區分技術事實、業務推論與需要確認事項。
- 指出合理使用、需要確認與可能不合理的使用。
- 提出 DBA 與業務單位可執行的確認事項與治理建議。
- 全文使用繁體中文。

知識邊界：
- 只能使用 supplied Business Consistency Context。
- 不可發明 database、schema、table、column、relationship 或業務規則。
- 同名欄位不代表業務語意必然相同。
- 資料字典未提供的內容視為未知。
- 沒有 Foreign Key 不代表不存在邏輯關聯。
- 無法確認的業務語意必須明確標示需要確認。
- Physical metadata 是技術事實；業務合理性判斷是分析結果。

輸出：
- 只建立 text 或 table section。
- table section 只能使用 table_id='column_usage'。
- 不可自行產生 table rows、columns 或 data；表格資料由應用程式控制。
- section 的名稱與順序可依 evidence 決定。
"""


def create_business_consistency_agent(
    model,
) -> Agent:
    return Agent(
        model=model,
        output_type=BusinessConsistencyReport,
        instructions=(
            BUSINESS_CONSISTENCY_AGENT_INSTRUCTIONS
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


def run_business_consistency_agent(
    *,
    report_context: dict,
    user_instruction: str,
    llm_cfg: dict,
) -> dict:
    """
    Execute the Business Consistency Agent.

    The application supplies context and user instruction.
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
        create_business_consistency_agent(
            model
        )
    )

    prompt = (
        "請根據以下 Business Consistency Context "
        "產生正式審查報告。\n\n"
        "USER INSTRUCTION:\n"
        + str(
            user_instruction
            or ""
        ).strip()
        + "\n\n"
        "BUSINESS CONSISTENCY CONTEXT:\n"
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




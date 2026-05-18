from __future__ import annotations

from memopilot.models import HistoricalMinute
from memopilot.token_estimate import estimate_tokens


SYSTEM_PROMPT = """你是企业会议纪要写作助理。

你必须只根据用户提供的历史会议纪要样例学习该公司的会议纪要正文写作风格。
不要使用外部公文模板，不要套用你预设的会议纪要格式或固定话术。
历史样例是唯一文风来源；本次会议原始记录是唯一事实来源。
"""


def build_generation_messages(
    history: list[HistoricalMinute],
    *,
    current_topic: str,
    transcript: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_user_prompt(
                history,
                current_topic=current_topic,
                transcript=transcript,
            ),
        },
    ]


def build_user_prompt(
    history: list[HistoricalMinute],
    *,
    current_topic: str,
    transcript: str,
) -> str:
    history_block = "\n\n".join(_format_history_item(index, item) for index, item in enumerate(history, 1))
    if not history_block:
        history_block = "暂无历史会议纪要样例。"

    return f"""请根据全部历史会议纪要样例，生成本次会议纪要正文。

工作方式：
1. 先在内部阅读全部历史样例，归纳它们的标题层级、段落组织、措辞习惯、事项展开方式、责任主体写法和详略程度。
2. 再阅读本次会议原始记录，提取应进入正式纪要的事实、数字、项目名称、责任事项和时间节点。
3. 最终只输出本次会议纪要正文，不输出你的分析过程。

硬性约束：
1. 只输出会议正文，不输出会议时间、地点、参会人员、主持人、记录人、附件等辅助信息。
2. 历史样例只用于学习文风，不得把历史样例中的事实、项目、人员、部门、时间节点复制到本次纪要中，除非本次原始记录也明确出现。
3. 本次会议原始记录是唯一事实来源；不得编造事实、数字、责任人、责任部门、时间节点或结论。
4. 不要使用外部通用模板。历史样例中不常见的表达方式，不要主动引入。
5. 可以压缩、归纳、重组口语化原始记录，但不能改变事实含义。
6. 如果本次原始记录信息不足，只写能被原始记录支持的内容。

历史会议纪要样例：
{history_block}

本次会议：
<本次会议主题>
{current_topic.strip()}
</本次会议主题>

<本次会议原始记录>
{transcript.strip()}
</本次会议原始记录>

请直接输出本次会议纪要正文。"""


def estimate_generation_input_tokens(
    history: list[HistoricalMinute],
    *,
    current_topic: str,
    transcript: str,
) -> int:
    messages = build_generation_messages(
        history,
        current_topic=current_topic,
        transcript=transcript,
    )
    return estimate_tokens("\n".join(message["content"] for message in messages))


def _format_history_item(index: int, item: HistoricalMinute) -> str:
    return f"""<历史会议纪要样例 index="{index}" id="{item.id}">
<会议主题>
{item.topic.strip()}
</会议主题>
<会议正文>
{item.body.strip()}
</会议正文>
</历史会议纪要样例>"""


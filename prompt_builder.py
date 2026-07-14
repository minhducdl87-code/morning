"""Build the daily-digest Gemini prompt from topic config + pre-fetched search context.
Hard rules embedded in the prompt prevent Gemini from inventing (hallucinating) URLs.
Moved out of generate_card.py to keep the orchestrator thin (see H1)."""


def build_daily_prompt(
    topics: dict,
    recent_titles: list,
    topic_contexts: dict,
    day_label: str,
    date_label: str,
    date_str: str,
    dedup_days: int,
    tone_guidance: str = "",
) -> str:
    """Build Gemini prompt with pre-fetched context. Hard rules prevent URL hallucination."""
    lines = [
        f"Hôm nay là {day_label}, {date_label}.",
        "Dựa trên dữ liệu tìm kiếm bên dưới, tổng hợp morning digest.\n"
    ]
    if tone_guidance:
        lines.append(tone_guidance)
        lines.append("")

    schema_fields = f'"date":"{date_str}","dayLabel":"{day_label}","dateLabel":"{date_label}"'

    for i, (key, topic) in enumerate(topics.items(), start=1):
        field   = topic["output_field"]
        min_i   = topic["min_items"]
        max_i   = topic["max_items"]
        instr   = topic["prompt_instruction"]
        schema  = topic["schema"]

        lines.append(f"── TASK {i}: {key} ──")
        lines.append(instr)

        ctx = topic_contexts.get(key, "")
        if ctx:
            lines.append(f"Dữ liệu tìm kiếm:\n{ctx}")
        else:
            # Critical: do NOT tell Gemini to invent. Allow Google Search grounding fallback.
            lines.append("(Không có dữ liệu tìm kiếm. Nếu được cấp Google Search tool, dùng nó. Nếu không, trả về mảng rỗng [].)")

        lines.append(f'Trả về field "{field}" với {min_i}-{max_i} items, schema mỗi item: {schema}\n')
        schema_fields += f',"{field}":[...]'

    if recent_titles:
        lines.append(f"TUYỆT ĐỐI KHÔNG lặp lại — các tin sau đã xuất hiện trong {dedup_days} ngày qua:")
        for t in recent_titles[:40]:
            lines.append(f"  - {t}")
        lines.append("(Nếu tin mới cùng chủ đề với các tin trên: chỉ chọn nếu có góc nhìn / diễn biến MỚI HẲN, và viết title khác hoàn toàn.)")
        lines.append("")

    lines.append("Trả về CHỈ JSON (không markdown, không text thêm):")
    lines.append("{" + schema_fields + "}")
    lines.append("")
    lines.append("HARD RULES (BẮT BUỘC):")
    lines.append("1. URL phải là URL THẬT, kiểm chứng được (sẽ được HEAD-check sau). KHÔNG bịa pattern plausible.")
    lines.append("2. Ưu tiên URL từ 'Dữ liệu tìm kiếm' / 'Dữ liệu GitHub' / Google Search citations.")
    lines.append("3. Nếu không chắc URL → set \"url\":\"\" (chuỗi rỗng) hơn là đoán. Item vẫn hiển thị với title+desc.")
    lines.append("4. Repo: name + url + stars phải khớp DỮ LIỆU GITHUB nguyên văn. KHÔNG tạo repo mới.")
    lines.append("5. Tiếng Việt ngắn gọn dễ hiểu. Trả về ĐẦY ĐỦ tất cả các field. Min_items là goal, không phải buộc — thà ít mà đúng.")

    return "\n".join(lines)

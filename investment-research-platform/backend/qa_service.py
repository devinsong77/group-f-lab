"""QAService — multi-session research report Q&A engine."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class QAService:
    MAX_HISTORY_MESSAGES = 50   # 单会话最大消息数
    MAX_CONTEXT_MESSAGES = 10   # 发送给LLM的最近消息数

    def __init__(
        self,
        storage,
        llm_client,
        llm_model: str,
        llm_fallback_model: str,
        data_dir: str = "data",
    ):
        self._storage = storage
        self._client = llm_client
        self._model = llm_model
        self._fallback_model = llm_fallback_model
        self._data_dir = data_dir
        self._sessions: dict[str, dict] = {}
        self._load()

    # ── persistence ───────────────────────────────────────────

    def _load(self):
        """从 data/qa_sessions.json 加载会话数据到内存"""
        path = os.path.join(self._data_dir, "qa_sessions.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._sessions = json.load(f)
                logger.info("Loaded %d QA sessions from %s", len(self._sessions), path)
            except Exception as e:
                logger.error("Failed to load QA sessions: %s", e)
                self._sessions = {}

    def _save(self):
        """将内存中的会话数据持久化到 data/qa_sessions.json"""
        path = os.path.join(self._data_dir, "qa_sessions.json")
        os.makedirs(self._data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._sessions, f, ensure_ascii=False, indent=2)

    # ── session CRUD ──────────────────────────────────────────

    def create_session(self, report_ids: list[str]) -> dict:
        """
        创建新会话。
        - 验证所有 report_id 存在且 parse_status == "completed"
        - 生成 session_id (uuid4)
        - 返回会话摘要（不含 messages）
        """
        # 验证研报
        for rid in report_ids:
            report = self._storage.get_report(rid)
            if report is None:
                raise ValueError("REPORTS_NOT_FOUND")
            if report.get("parse_status") != "completed":
                raise ValueError("REPORTS_NOT_PARSED")

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "session_id": session_id,
            "title": "新会话",
            "report_ids": report_ids,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        self._sessions[session_id] = session
        self._save()
        logger.info("Created QA session %s for reports %s", session_id, report_ids)

        return self._session_summary(session)

    def list_sessions(self) -> list[dict]:
        """
        返回所有会话摘要列表（不含 messages 内容，但含 message_count）。
        按 updated_at 降序排列。
        """
        summaries = [self._session_summary(s) for s in self._sessions.values()]
        summaries.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return summaries

    def get_session(self, session_id: str) -> dict:
        """返回完整会话（含所有 messages）。"""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")
        return {**session}

    def delete_session(self, session_id: str) -> None:
        """删除会话。"""
        if session_id not in self._sessions:
            raise ValueError("SESSION_NOT_FOUND")
        del self._sessions[session_id]
        self._save()
        logger.info("Deleted QA session %s", session_id)

    # ── core Q&A ──────────────────────────────────────────────

    def ask(self, session_id: str, question: str) -> dict:
        """
        核心问答方法。
        返回 assistant message dict。
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")

        # 收集关联研报的解析数据
        reports_context = []
        for rid in session["report_ids"]:
            parsed = self._storage.get_parsed_report(rid)
            if parsed:
                reports_context.append({
                    "report_id": rid,
                    "title": parsed.get("title", ""),
                    "raw_text": parsed.get("raw_text", ""),
                    "key_points": parsed.get("key_points", ""),
                    "stock_name": parsed.get("stock_name", ""),
                })

        # 构建 prompt 和 messages
        system_prompt = self._build_system_prompt(reports_context)
        messages = self._build_messages(session, question, system_prompt)

        # 调用 LLM（主备降级）
        try:
            result = self._call_llm(messages)
        except Exception as e:
            logger.error("QA LLM call failed: %s", e)
            raise RuntimeError("QA_FAILED") from e

        # 创建 user message
        user_msg = self._create_message("user", question)
        session["messages"].append(user_msg)

        # 创建 assistant message（sources 去重）
        deduped_sources = self._deduplicate_sources(result.get("sources", []))
        assistant_msg = self._create_message(
            "assistant",
            result.get("answer", ""),
            source_type=result.get("source_type", "ai_generated"),
            sources=deduped_sources,
        )
        session["messages"].append(assistant_msg)

        # 首条问题时更新 title
        user_messages = [m for m in session["messages"] if m["role"] == "user"]
        if len(user_messages) == 1:
            session["title"] = question[:30]

        # 更新时间戳
        session["updated_at"] = datetime.now(timezone.utc).isoformat()

        # 限制消息数量，超过则删除最早的
        while len(session["messages"]) > self.MAX_HISTORY_MESSAGES:
            session["messages"].pop(0)

        self._save()
        return assistant_msg

    # ── prompt construction ───────────────────────────────────

    def _build_system_prompt(self, reports_context: list[dict]) -> str:
        """构建系统提示词，包含研报原文内容。"""
        reports_section = ""
        for i, rc in enumerate(reports_context, 1):
            reports_section += (
                f"\n=== 研报 {i}: {rc['title']} (ID: {rc['report_id']}) ===\n"
                f"{rc['raw_text']}\n"
                f"=== 研报 {i} 结束 ===\n"
            )

        prompt = (
            "你是专业的金融研报分析助手。请基于以下提供的研报内容回答用户问题。\n\n"
            "【回答规则】\n"
            "1. 如果答案可以从研报中找到，必须引用原文并标注来源。\n"
            "2. 如果研报中没有相关信息，可以基于专业金融知识补充回答，但必须明确标注「此为AI补充分析，非研报原文」。\n"
            "3. 对于混合类型，先给出研报相关内容，再补充AI分析。\n\n"
            "【返回格式】\n"
            "请严格返回以下JSON格式（不要包含其他内容）：\n"
            '{\n'
            '  "answer": "回答内容（支持markdown格式）",\n'
            '  "source_type": "report_based 或 ai_generated 或 mixed",\n'
            '  "sources": [\n'
            '    {\n'
            '      "report_id": "研报ID",\n'
            '      "report_title": "研报标题",\n'
            '      "quote": "引用的研报原文片段（尽量精确到句子级别）"\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "【说明】\n"
            "- sources 仅在引用研报内容时填写，ai_generated 时 sources 为空数组。\n"
            "- source_type 三种取值：report_based（完全基于研报）、ai_generated（完全AI生成）、mixed（混合）。\n\n"
            "【研报内容】\n"
            f"{reports_section}"
        )
        return prompt

    def _build_messages(self, session: dict, question: str, system_prompt: str) -> list[dict]:
        """
        构建发送给LLM的完整消息列表。
        - system message
        - 最近 MAX_CONTEXT_MESSAGES 条历史消息
        - 当前用户问题
        """
        msgs: list[dict] = [{"role": "system", "content": system_prompt}]

        # 取最近的历史消息
        history = session.get("messages", [])
        recent = history[-self.MAX_CONTEXT_MESSAGES:] if len(history) > self.MAX_CONTEXT_MESSAGES else history
        for m in recent:
            msgs.append({"role": m["role"], "content": m["content"]})

        # 当前问题
        msgs.append({"role": "user", "content": question})
        return msgs

    # ── streaming Q&A ────────────────────────────────────────

    def _build_stream_system_prompt(self, reports_context: list[dict]) -> str:
        """构建流式问答专用的系统提示词。

        与非流式版本不同，这里要求 LLM 先输出 markdown 回答，
        最后在末尾输出 <!--SOURCES_JSON--> 标记块来标注来源。
        """
        reports_section = ""
        for i, rc in enumerate(reports_context, 1):
            reports_section += (
                f"\n=== 研报 {i}: {rc['title']} (ID: {rc['report_id']}) ===\n"
                f"{rc['raw_text']}\n"
                f"=== 研报 {i} 结束 ===\n"
            )

        prompt = (
            "你是专业的金融研报分析助手。基于提供的研报内容回答用户问题。\n\n"
            "回答要求：\n"
            "1. 使用markdown格式回答，支持加粗、列表等格式\n"
            "2. 如果答案可以从研报中找到，优先引用研报原文\n"
            "3. 如果研报中没有相关信息，可以基于专业金融知识补充回答\n\n"
            "回答完成后，在最末尾添加来源标注（固定格式，不要修改标记）：\n"
            "<!--SOURCES_JSON-->\n"
            '{"source_type": "report_based或ai_generated或mixed", '
            '"sources": [{"report_id": "研报ID", "report_title": "研报标题", '
            '"quote": "引用原文片段"}]}\n'
            "<!--/SOURCES_JSON-->\n\n"
            "注意：\n"
            "- source_type: report_based(基于研报), ai_generated(AI生成), mixed(综合)\n"
            "- sources: 仅在引用研报内容时填写，ai_generated时为空数组\n"
            "- 每份研报的引用不要重复相同的内容\n\n"
            f"【研报内容】\n{reports_section}"
        )
        return prompt

    def _parse_stream_sources(self, full_text: str) -> tuple[str, str, list[dict]]:
        """从流式 LLM 完整输出中提取回答正文和来源标注。

        Returns:
            (answer, source_type, sources)
        """
        import re as _re
        pattern = r"<!--SOURCES_JSON-->\s*(.*?)\s*<!--/SOURCES_JSON-->"
        match = _re.search(pattern, full_text, _re.DOTALL)
        if match:
            answer = full_text[:match.start()].strip()
            try:
                meta = json.loads(match.group(1).strip())
                source_type = meta.get("source_type", "ai_generated")
                sources = meta.get("sources", [])
                return answer, source_type, sources
            except (json.JSONDecodeError, TypeError):
                pass
        return full_text.strip(), "ai_generated", []

    def ask_stream(self, session_id: str, question: str):
        """流式问答生成器，yield SSE 格式字符串。

        流程：
        1. 验证 session，获取研报上下文
        2. 构建 messages（含历史上下文）
        3. 使用 stream=True 调用 LLM，逐 chunk yield token 事件
        4. 收集完整响应后解析 sources，去重
        5. 保存 user/assistant message 到 session
        6. yield done 事件
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")

        # 收集关联研报的解析数据
        reports_context = []
        for rid in session["report_ids"]:
            parsed = self._storage.get_parsed_report(rid)
            if parsed:
                reports_context.append({
                    "report_id": rid,
                    "title": parsed.get("title", ""),
                    "raw_text": parsed.get("raw_text", ""),
                    "key_points": parsed.get("key_points", ""),
                    "stock_name": parsed.get("stock_name", ""),
                })

        # 构建流式专用 prompt
        system_prompt = self._build_stream_system_prompt(reports_context)
        messages = self._build_messages(session, question, system_prompt)

        start_time = time.time()
        full_content = ""
        sent_length = 0
        last_error = None
        success = False

        for model in (self._model, self._fallback_model):
            try:
                logger.info("QA stream calling LLM model: %s", model)
                # 如果上一个模型部分输出后失败，发送 reset 让前端清空
                if full_content:
                    yield f"data: {json.dumps({'type': 'reset'}, ensure_ascii=False)}\n\n"
                    full_content = ""
                    sent_length = 0

                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    stream=True,
                )

                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        full_content += delta

                        # 检测是否进入 SOURCES 标记区域，标记及之后的内容不发送给前端
                        marker_pos = full_content.find("<!--")
                        safe_end = marker_pos if marker_pos >= 0 else len(full_content)

                        if safe_end > sent_length:
                            to_send = full_content[sent_length:safe_end]
                            sent_length = safe_end
                            yield f"data: {json.dumps({'type': 'token', 'content': to_send}, ensure_ascii=False)}\n\n"

                success = True
                break  # 成功完成，退出模型循环
            except Exception as e:
                logger.error("QA stream model %s failed: %s", model, e)
                last_error = e

        if not success:
            logger.error("QA stream all models failed: %s", last_error)
            yield f"data: {json.dumps({'type': 'error', 'message': '问答生成失败'}, ensure_ascii=False)}\n\n"
            return

        # 解析来源
        elapsed_ms = int((time.time() - start_time) * 1000)
        answer, source_type, sources = self._parse_stream_sources(full_content)
        sources = self._deduplicate_sources(sources)

        # 保存消息到 session
        user_msg = self._create_message("user", question)
        session["messages"].append(user_msg)

        assistant_msg = self._create_message(
            "assistant",
            answer,
            source_type=source_type,
            sources=sources,
            elapsed_ms=elapsed_ms,
        )
        session["messages"].append(assistant_msg)

        # 首条问题时更新 title
        user_messages = [m for m in session["messages"] if m["role"] == "user"]
        if len(user_messages) == 1:
            session["title"] = question[:30]

        session["updated_at"] = datetime.now(timezone.utc).isoformat()

        # 限制消息数量
        while len(session["messages"]) > self.MAX_HISTORY_MESSAGES:
            session["messages"].pop(0)

        self._save()

        # yield done 事件
        yield f"data: {json.dumps({'type': 'done', 'message': assistant_msg}, ensure_ascii=False)}\n\n"

    # ── LLM call with fallback ────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> dict:
        """调用LLM，支持主备降级。返回解析后的 dict。"""
        last_error = None

        for model in (self._model, self._fallback_model):
            try:
                logger.info("QA calling LLM model: %s", model)
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                )
                content = response.choices[0].message.content
                return self._parse_llm_response(content)
            except Exception as e:
                logger.error("QA LLM model %s failed: %s", model, e)
                last_error = e

        raise last_error  # type: ignore[misc]

    def _parse_llm_response(self, content: str) -> dict:
        """
        对LLM返回内容做容错解析。
        - 尝试 json.loads
        - 如果被 ```json ... ``` 包裹，先提取
        - 解析失败则降级为纯文本回答
        """
        text = content.strip()

        # 提取 ```json ... ``` 包裹的内容
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        try:
            result = json.loads(text)
            # 确保必要字段存在
            if "answer" not in result:
                result["answer"] = text
            if "source_type" not in result:
                result["source_type"] = "ai_generated"
            if "sources" not in result:
                result["sources"] = []
            return result
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse LLM JSON response, falling back to plain text")
            return {
                "answer": content.strip(),
                "source_type": "ai_generated",
                "sources": [],
            }

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_sources(sources: list[dict]) -> list[dict]:
        """根据 report_id + quote 前100字符的组合去重。"""
        seen: set[tuple[str, str]] = set()
        result: list[dict] = []
        for src in sources:
            key = (src.get("report_id", ""), src.get("quote", "")[:100])
            if key not in seen:
                seen.add(key)
                result.append(src)
        return result

    def _create_message(self, role: str, content: str, **kwargs) -> dict:
        """创建消息dict，包含 id, role, content, timestamp 及额外字段。"""
        msg = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        msg.update(kwargs)
        return msg

    def _session_summary(self, session: dict) -> dict:
        """返回会话摘要（不含 messages 内容）。"""
        return {
            "session_id": session["session_id"],
            "title": session["title"],
            "report_ids": session["report_ids"],
            "message_count": len(session.get("messages", [])),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

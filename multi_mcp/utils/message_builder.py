"""Message builder for LLM requests - stateless and simple."""

import html
from dataclasses import dataclass, field


@dataclass
class MessageBuilder:
    """Builds LLM message lists from components.

    Stateless: each instance builds ONE message list, then is discarded.

    Example:
        messages = await (
            MessageBuilder(system_prompt=CHAT_PROMPT, base_path=base_path, thread_id=thread_id)
            .add_conversation_history()
            .add_repository_context()
            .add_files(relevant_files)
            .add_user_message(content)
            .build()
        )
    """

    system_prompt: str
    base_path: str | None = None
    thread_id: str | None = None
    include_history: bool = True

    # Internal state - intent flags (no actual loading until build())
    _want_repo_context: bool = field(default=False, init=False)
    _files_to_embed: list[str] | None = field(default=None, init=False)
    _user_message_content: str | None = field(default=None, init=False)
    _user_message_wrap_xml: bool = field(default=True, init=False)
    _user_message_escape_html: bool = field(default=True, init=False)
    _user_message_built: bool = field(default=False, init=False)

    def add_conversation_history(self) -> "MessageBuilder":
        """Mark that conversation history should be loaded.

        This is NOT async - the actual history loading happens in build().
        """
        self.include_history = True
        return self

    def add_repository_context(self) -> "MessageBuilder":
        """Mark that repository context should be included.

        Context will be loaded in build() ONLY if this is the first call (not continuation).
        Context is loaded from disk with mtime-based caching in build_repository_context().
        """
        if not self.base_path:
            return self

        self._want_repo_context = True
        return self

    def add_files(self, files: list[str] | None) -> "MessageBuilder":
        """Mark that files should be included.

        Files will be embedded in build() ONLY if this is the first call (not continuation).
        Files are wrapped in <EDITABLE_FILES>.
        """
        if not files:
            return self

        self._files_to_embed = files
        return self

    def add_user_message(self, content: str, wrap_xml: bool = True, escape_html: bool = True) -> "MessageBuilder":
        """Add user message (call this LAST after all context).

        Args:
            content: User message content
            wrap_xml: Whether to wrap in <USER_MESSAGE> tags (default: True)
            escape_html: Whether to HTML-escape content (default: True)

        Note: Can only be called once per builder instance.
        """
        if self._user_message_built:
            raise ValueError("add_user_message() can only be called once per MessageBuilder instance")

        # Store the raw content and processing flags - actual processing happens in build()
        self._user_message_content = content
        self._user_message_wrap_xml = wrap_xml
        self._user_message_escape_html = escape_html
        self._user_message_built = True
        return self

    async def build(self) -> list[dict]:
        """Build final message list.

        First call: [system, user (with repo + files)]
        Continuation: [...history, user (just message)]

        Returns:
            List of message dicts ready for LLM API
        """
        if not self._user_message_built or self._user_message_content is None:
            raise ValueError("Must call add_user_message() before build()")

        # Check history ONCE to determine if this is a continuation
        history: list = []
        is_continuation = False

        if self.include_history and self.thread_id:
            from multi_mcp.memory.store import get_messages

            history = await get_messages(self.thread_id)
            if history:
                is_continuation = True

        # Build the user message parts based on continuation status
        user_message_parts: list[str] = []

        if not is_continuation:
            # First call: Load repository context and files NOW
            if self._want_repo_context and self.base_path:
                from multi_mcp.utils.repository import build_repository_context

                repo_context = build_repository_context(self.base_path)
                if repo_context:
                    user_message_parts.append(repo_context)

            if self._files_to_embed and self.base_path:
                from multi_mcp.utils.files import embed_files_for_expert

                embedded_files = embed_files_for_expert(self._files_to_embed, self.base_path)
                user_message_parts.append(embedded_files)

        # Process and add the user message
        user_content = self._user_message_content
        if self._user_message_escape_html:
            user_content = html.escape(user_content)

        if self._user_message_wrap_xml:
            user_content = f"<USER_MESSAGE>\n{user_content}\n</USER_MESSAGE>"

        user_message_parts.append(user_content)

        # Combine all parts
        full_user_message = "\n\n".join(user_message_parts)

        # Build final message list
        if is_continuation:
            # Continuation: history + new user message (no repo/files)
            if not self.thread_id:
                raise ValueError("thread_id required for continuation")
            result: list[dict] = [dict(msg) for msg in history]
            result.append({"role": "user", "content": full_user_message})
            return result
        else:
            # First call: system + user (with repo + files if requested)
            return [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": full_user_message},
            ]

"""CLI component for interactive chat using agentscope-based memory tools."""

import asyncio
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import execute_python_code, Toolkit, ToolResponse
from loguru import logger

from .compactor import Compactor
from .context_checker import ContextChecker
from .summarizer import Summarizer
from ..tools import browser_use, FileIO, MemorySearch, Shell
from ....core.op import BaseOp
from ....core.utils import format_messages

# name + desc + "{working_dir}/skills/{skill_name}/SKILL.md"


class CliAgent(BaseOp):
    """CLI agent for interactive chat with memory management."""

    def __init__(
        self,
        working_dir: str,
        max_iters: int = 50,
        vector_weight: float = 0.7,
        candidate_multiplier: float = 3.0,
        context_window_tokens: int = 128000,
        reserve_tokens: int = 36000,
        keep_recent_tokens: int = 20000,
        language: str = "zh",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.working_dir: str = working_dir
        Path(self.working_dir).mkdir(parents=True, exist_ok=True)
        self.max_iters: int = max_iters
        self.vector_weight: float = vector_weight
        self.candidate_multiplier: float = candidate_multiplier
        self.context_window_tokens: int = context_window_tokens
        self.reserve_tokens: int = reserve_tokens
        self.keep_recent_tokens: int = keep_recent_tokens
        self.language: str = language

        # Initialize message history
        self.messages: list[Msg] = []
        self.previous_summary: str = ""
        self.summary_tasks: list[asyncio.Task] = []

        # Initialize toolkit
        self.toolkit = self._create_file_toolkit()
        self.toolkit.register_tool_function(browser_use)
        self.toolkit.register_tool_function(execute_python_code)
        self.toolkit.register_tool_function(self.memory_search)
        self.toolkit.register_tool_function(self.execute_shell_command)

        # Register agent skills
        skill_dir = Path(self.working_dir) / "skills"
        self._download_skills_from_github(skill_dir)

    def _create_file_toolkit(self):
        """Create a toolkit with file operations."""

        toolkit = Toolkit()
        file_io = FileIO(working_dir=self.working_dir)
        toolkit.register_tool_function(file_io.read)
        toolkit.register_tool_function(file_io.write)
        toolkit.register_tool_function(file_io.edit)

        return toolkit

    def _find_skills_then_register(self, path: str, target_dir: Path, exist: bool = False) -> None:
        # Recursively find all directories containing SKILL.md
        skill_paths = []
        for root, _, files in os.walk(path):
            if "SKILL.md" in files:
                skill_paths.append(Path(root))

        # Copy each skill directory to target
        for skill_path in skill_paths:
            dest = target_dir / skill_path.name
            if not exist:
                shutil.copytree(skill_path, dest)
            self.toolkit.register_agent_skill(dest)

        print(f"Successfully downloaded {len(skill_paths)} skills to {str(target_dir)}")

    def _download_skills_from_github(
        self,
        skill_dir: str,
        repo_url: str = "https://github.com/anthropics/skills.git",
    ) -> None:
        """
        Download skills from github repository to the specified path.
        Args:
            skill_dir: Target directory to store the skills
            repo_url: GitHub repository URL (default: anthropics/skills)
        """
        target_dir = Path(skill_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Check if skills directory already exists and is not empty
        if any(target_dir.iterdir()):
            logger.info(f"Skill directory {skill_dir} already exists and is not empty. Skipping download.")
            self._find_skills_then_register(skill_dir, target_dir, True)
            return

        # Clone to a temporary directory first
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_repo_path = Path(temp_dir) / "skills"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, str(temp_repo_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self._find_skills_then_register(temp_repo_path, target_dir)
            except subprocess.CalledProcessError as e:
                logger.exception(f"Failed to clone repository: {e}")
                if e.stderr:
                    logger.exception(f"Error output: {e.stderr}")
                raise
            except Exception as e:
                logger.exception(f"Error downloading skills: {e}")
                raise

    def add_summary_task(self, messages: list[Msg]):
        """Add summary task to queue."""
        remaining_tasks = []
        for task in self.summary_tasks:
            if task.done():
                exc = task.exception()
                if exc is not None:
                    logger.exception(f"Summary task failed: {exc}")
                else:
                    result = task.result()
                    logger.info(f"Summary task completed: {result}")
            else:
                remaining_tasks.append(task)
        self.summary_tasks = remaining_tasks

        # Create a toolkit for the summarizer
        toolkit = self._create_file_toolkit()

        # Create summarizer instance
        memory_path = Path(self.working_dir) / "memory"
        summarizer = Summarizer(
            working_dir=self.working_dir,
            memory_dir=str(memory_path),
            memory_compact_threshold=int(self.context_window_tokens * 0.7),
            token_counter=self.as_token_counter,
            toolkit=toolkit,
            as_llm=self.as_llm,
            as_llm_formatter=self.as_llm_formatter,
            language=self.language if self.language == "zh" else "",
            console_enabled=False,  # We disable the terminal printing to avoid messy outputs
        )

        # Create summary task
        summary_task = asyncio.create_task(
            summarizer.call(
                messages=messages,
                service_context=self.service_context,
            ),
        )
        self.summary_tasks.append(summary_task)

    async def new(self) -> str:
        """Reset conversation history using summary."""
        if not self.messages:
            self.messages.clear()
            self.previous_summary = ""
            return "No history to reset."

        self.add_summary_task(self.messages)

        self.messages.clear()
        self.previous_summary = ""
        return "History saved to memory files and reset."

    async def context_check(self) -> dict:
        """Check if messages exceed token limits."""
        # Create context checker
        checker = ContextChecker(
            memory_compact_threshold=self.context_window_tokens - self.reserve_tokens,
            memory_compact_reserve=self.keep_recent_tokens,
            token_counter=self.as_token_counter,
        )

        return await checker.call(
            messages=self.messages,
            service_context=self.service_context,
        )

    async def compact(self, force_compact: bool = False) -> str:
        """Compact history then reset."""
        if not self.messages:
            return "No history to compact."

        # Check and find cut point
        messages_to_compact, messages_to_keep, _ = await self.context_check()
        tokens_before = len(self.messages)

        if force_compact:
            messages_to_summarize = self.messages
            left_messages = []
        elif not messages_to_compact:
            return "History is within token limits, no compaction needed."
        else:
            messages_to_summarize = messages_to_compact
            left_messages = messages_to_keep

        # Create compactor
        compactor = Compactor(
            memory_compact_threshold=self.context_window_tokens - self.reserve_tokens,
            token_counter=self.as_token_counter,
            as_llm=self.as_llm,
            as_llm_formatter=self.as_llm_formatter,
            language=self.language if self.language == "zh" else "",
            console_enabled=False,  # We disable the terminal printing to avoid messy outputs
        )

        summary_content = await compactor.call(
            messages=messages_to_summarize,
            previous_summary=self.previous_summary,
            service_context=self.service_context,
        )

        self.add_summary_task(messages=messages_to_summarize)

        # Assemble final messages
        self.messages = left_messages
        self.previous_summary = summary_content

        return f"History compacted from {tokens_before} messages."

    def format_history(self) -> str:
        """Format history messages."""
        return format_messages(
            messages=self.messages,
            add_index=False,
            add_reasoning=False,
            strip_markdown_headers=False,
        )

    async def _build_messages(self, query: str) -> list[Msg]:
        """Build system prompt message."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")

        # Create system prompt
        system_prompt = self.prompt_format(
            "system_prompt",
            workspace_dir=self.working_dir,
            current_time=current_time,
            has_previous_summary=bool(self.previous_summary),
            previous_summary=self.previous_summary or "",
        )

        logger.info(f"[{self.__class__.__name__}] system_prompt: {system_prompt}")

        # Build message list
        messages = [Msg(name="system", role="system", content=system_prompt)]
        messages.extend(self.messages)
        messages.append(Msg(name="user", role="user", content=query))

        return messages

    async def memory_search(self, query: str, max_results: int = 5, min_score: float = 0.1) -> ToolResponse:
        """
        Mandatory recall step: semantically search MEMORY.md + memory/*.md (and optional session transcripts)
        before answering questions about prior work, decisions, dates, people, preferences, or todos;
        returns top snippets with path + lines.

        Args:
            query: The semantic search query to find relevant memory snippets
            max_results: Maximum number of search results to return (optional), default is 5
            min_score: Minimum similarity score threshold for results (optional), default is 0.1

        Returns:
            Search results as formatted string
        """
        search_tool = MemorySearch(
            vector_weight=self.vector_weight,
            candidate_multiplier=self.candidate_multiplier,
        )
        search_result = await search_tool.call(
            query=query,
            max_results=max_results,
            min_score=min_score,
            service_context=self.service_context,
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=search_result,
                ),
            ],
        )

    async def execute_shell_command(self, command: str, timeout: int = 60) -> ToolResponse:
        """Execute given command and return the return code, standard output and
        error within <returncode></returncode>, <stdout></stdout> and
        <stderr></stderr> tags.

        Args:
            command (`str`):
                The shell command to execute.
            timeout (`int`, defaults to `60`):
                The maximum time (in seconds) allowed for the command to run.
                Default is 60 seconds.

        Returns:
            `ToolResponse`:
                The tool response containing the return code, standard output, and
                standard error of the executed command. If timeout occurs, the
                return code will be -1 and stderr will contain timeout information.
        """
        shell_tool = Shell(working_dir=self.working_dir)
        shell_result = await shell_tool.execute_shell_command(
            command=command,
            timeout=timeout,
        )
        return shell_result

    async def execute(self):
        """Execute the agent."""
        _ = await self.compact(force_compact=False)

        # Build messages for the agent
        query = self.context.query
        messages = await self._build_messages(query)

        # Create the ReAct agent
        agent = ReActAgent(
            name="reme_cli_agent",
            model=self.as_llm,
            sys_prompt=messages[0].content,  # System prompt
            formatter=self.as_llm_formatter,
            toolkit=self.toolkit,
            max_iters=self.max_iters,
        )

        # We disable the terminal printing to avoid messy outputs
        agent.set_console_output_enabled(False)

        self.messages = messages[1:]  # remove the first SYSTEM message
        agent.memory.content.clear()

        # Stream processing state
        in_thinking = False
        in_answer = False

        # obtain the printing messages from the agent in a streaming way
        last_text_content = ""
        last_think_content = ""
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(self.messages),
        ):
            # print(msg, last)
            content_blocks = msg.get_content_blocks()
            for block in content_blocks:
                if block["type"] == "thinking":
                    if not in_thinking and len(block["thinking"]) > len(last_think_content):
                        print("\033[90m\nThinking: ", end="", flush=True)
                        in_thinking = True
                    print(block["thinking"][len(last_think_content) :], end="", flush=True)
                    last_think_content = block["thinking"]
                elif block["type"] == "text":
                    if in_thinking:
                        print("\033[0m")  # reset color after thinking
                        in_thinking = False
                    if not in_answer:
                        print("\nRemy: ", end="", flush=True)
                        in_answer = True
                    print(block["text"][len(last_text_content) :], end="", flush=True)
                    last_text_content = block["text"]
                elif block["type"] == "tool_use":
                    if in_thinking:
                        print("\033[0m")  # reset color after thinking
                        in_thinking = False
                    if last:
                        print(f"\033[36m  -> Executing Tool: name={block['name']}, input={block['input']}\033[0m")
                elif block["type"] == "tool_result":
                    if last:
                        last_think_content = ""  # reset for further thinking
                        print(f"\033[36m  -> Tool Result for `{block['name']}`: {block['output'][0]['text']}\033[0m")
                else:
                    print(f"Unknown block type: {block['type']}")
            if last:
                self.messages.append(msg)

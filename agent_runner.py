"""create-envvars-docs.py / create-cli-docs.py が共有するエージェント起動部。

両スクリプトは「1 文書 1 セッションでエージェントに調査させる」点で共通するため、
起動するエージェント (codex / pi) の差分だけをこのモジュールに集める。
プロンプト本文・候補選択・試行記録は各スクリプト側のまま。

- codex: `codex exec` の `--output-last-message` に最終応答が出る。
- pi: `--print` の stdout が最終応答、stderr が診断ログ。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

RUNNERS = ("codex", "pi")

CODEX_MODEL = "gpt-6-luna"
CODEX_THINKING = "high"

PI_PROVIDER = "ollama-cloud"
PI_MODEL = "deepseek-v4.1-flash:1017"
PI_THINKING = "high"
# 既定の 4 ツールに絞る。web 系拡張や MCP、プロジェクトの skill を読み込むと
# 「Strata のソースだけを一次情報にする」調査基準から外れた挙動になりうるため、
# print モードでは明示的に無効化する。
PI_TOOLS = "read,bash,edit,write"
# pi (DeepSeek) は調査基準の「全部挙げる」「結果まで追う」を字面どおりに広げ、
# codex の 2〜3 倍の分量になりやすい。常用の pi 設定には手を入れず、
# この起動に限って system prompt へ分量の歯止めを追記する。
# 目安は codex が作った既存文書の分布（中央値 約 6KB、9 割が 8KB 以下）。
PI_DOC_BUDGET_BYTES = 8000
PI_APPEND_SYSTEM_PROMPT = f"""\
# 調査文書の分量

調査は依頼どおり丁寧に行い、文書は読み手が使う事実に絞って短く書く。

- 文書 1 件の大きさは 4000〜{PI_DOC_BUDGET_BYTES} バイト（`wc -c`）を目安にする。調査基準の各項目は満たしつつ、各項目を数行で済ませる。
- 対象以外の環境変数・CLI option・内部の仕組みは、名前と必要な値と参照先を 1 行で書くだけにする。それらの判定表、分岐の全列挙、内部データ構造の説明は書かない。
- 同じ事実を複数の節に書かない。表に書いたことを本文で言い直さない。
- `path:line` は主張の近くに置く。末尾の根拠節は本文の引用を繰り返さず、主要な箇所 5〜8 行にする。
- 対象の挙動の理解に必要か迷う事項（隣接機能の詳細、同梱台帳との細かな差、自己テストの話など）は書かない。
- 書き終えたら `wc -c` で文書の大きさを測る。{PI_DOC_BUDGET_BYTES} バイトを超えていたら、上の優先度の低いものから削り、`path:line` の根拠は残したまま {PI_DOC_BUDGET_BYTES} バイト以下にしてから作業を終える。
"""

FAILURE_LOG_LINES = 60


@dataclass(frozen=True)
class RunnerConfig:
    """実際に起動するコマンドを決めるのに十分な情報。"""

    runner: str
    model: str
    thinking: str
    provider: str
    tools: str
    repo_root: Path


def add_runner_args(parser: argparse.ArgumentParser) -> None:
    """--runner と、ランナー共通のモデル指定オプションを登録する。"""
    parser.add_argument(
        "-r",
        "--runner",
        choices=RUNNERS,
        default="codex",
        help="調査・作成を任せるエージェント (default: codex)",
    )
    parser.add_argument(
        "--model",
        metavar="NAME",
        default=None,
        help=(
            f"エージェントのモデル名 (default: codex={CODEX_MODEL}, pi={PI_MODEL})"
        ),
    )
    parser.add_argument(
        "--thinking",
        metavar="LEVEL",
        default=None,
        help=(
            "推論の強さ。codex では model_reasoning_effort、pi では --thinking "
            f"(default: {CODEX_THINKING})"
        ),
    )
    parser.add_argument(
        "--provider",
        metavar="NAME",
        default=None,
        help=f"--runner pi のときのプロバイダ (default: {PI_PROVIDER}、codex では無視)",
    )
    parser.add_argument(
        "--tools",
        metavar="LIST",
        default=None,
        help=(
            f"--runner pi のときのツール一覧 (default: {PI_TOOLS}、"
            "空文字にすると pi 側の既定。codex では無視)"
        ),
    )


def resolve_runner(args: argparse.Namespace, repo_root: Path) -> RunnerConfig:
    """argparse の結果からランナーごとの既定値を埋めて確定させる。"""
    runner = args.runner
    if runner == "codex":
        model = args.model or CODEX_MODEL
        thinking = args.thinking or CODEX_THINKING
        provider = ""
        tools = ""
    else:
        model = args.model or PI_MODEL
        thinking = args.thinking or PI_THINKING
        provider = args.provider or PI_PROVIDER
        tools = PI_TOOLS if args.tools is None else args.tools

    return RunnerConfig(
        runner=runner,
        model=model,
        thinking=thinking,
        provider=provider,
        tools=tools,
        repo_root=repo_root,
    )


def describe(config: RunnerConfig) -> str:
    """起動時に 1 行表示する実行内容。"""
    if config.runner == "codex":
        return f"runner=codex model={config.model} reasoning_effort={config.thinking}"
    parts = [
        f"runner=pi provider={config.provider}",
        f"model={config.model}",
        f"thinking={config.thinking}",
    ]
    if config.tools:
        parts.append(f"tools={config.tools}")
    return " ".join(parts)


def build_command(config: RunnerConfig, prompt: str, last_message_path: Path) -> list[str]:
    """1 セッション分のコマンドラインを作る。"""
    if config.runner == "codex":
        return [
            "codex",
            "exec",
            "--model",
            config.model,
            "--config",
            f"model_reasoning_effort={config.thinking}",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(config.repo_root),
            "--output-last-message",
            str(last_message_path),
            prompt,
        ]

    command = [
        "pi",
        "--provider",
        config.provider,
        "--model",
        config.model,
        "--thinking",
        config.thinking,
        "--print",
        "--no-session",
        "--no-approve",
        "--no-extensions",
        "--no-mcp",
        "--no-skills",
        "--append-system-prompt",
        PI_APPEND_SYSTEM_PROMPT,
    ]
    if config.tools:
        command += ["--tools", config.tools]
    # プロンプトが `-` で始まってもオプションとして解釈させない
    command += ["--", prompt]
    return command


def run_prompt(config: RunnerConfig, prompt: str, *, temp_prefix: str) -> tuple[int, str, str]:
    """エージェントを 1 回起動し、(終了コード, 最終応答, 失敗時の末尾ログ) を返す。

    最終応答は codex では --output-last-message、pi では stdout。
    ログは一時ディレクトリに書き、返り値の末尾ログ以外では残さない。
    """
    with tempfile.TemporaryDirectory(prefix=temp_prefix) as temp_dir:
        temp_path = Path(temp_dir)
        last_message_path = temp_path / "last-message.md"
        log_path = temp_path / f"{config.runner}.log"
        command = build_command(config, prompt, last_message_path)

        if config.runner == "codex":
            with log_path.open("w", encoding="utf-8") as log_file:
                result = subprocess.run(
                    command,
                    cwd=config.repo_root,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
            last_message = (
                last_message_path.read_text(encoding="utf-8").strip()
                if last_message_path.is_file()
                else ""
            )
        else:
            # print モードの stdout は最終応答テキストだけ。診断は stderr に出る。
            result = subprocess.run(
                command,
                cwd=config.repo_root,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
            last_message = result.stdout.strip()
            log_path.write_text(result.stderr, encoding="utf-8")

        log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        failure_log = (
            "\n".join(log_lines[-FAILURE_LOG_LINES:]) if result.returncode != 0 else ""
        )
    return result.returncode, last_message, failure_log


def check_binary(config: RunnerConfig) -> bool:
    """起動コマンドが PATH 上に在るか。無ければ理由を表示して False。"""
    binary = config.runner
    if shutil.which(binary) is None:
        print(
            f"{binary} が見つかりません。PATH を確認するか、別の --runner を使ってください。",
            file=sys.stderr,
        )
        return False
    return True

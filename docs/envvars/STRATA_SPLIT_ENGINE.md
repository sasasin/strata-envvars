# `STRATA_SPLIT_ENGINE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata launch` が all-cards split engine（`strata-split-N`）を選ぶモードを指定します。これは Strata の Python 制御層が読む値で、split engine の GPU kernel 自身が読む変数としては使われていません。未指定時の `auto` は条件に合う環境で選択し、`on` は選択を明示的に要求し、`off` は選択を止めます。対象の設定値は `strata_control.split_engine.mode()` が決めます。

## 値と判定

環境変数の値を `strip()` して空でなければ、その文字列を `lower()` した完全一致で判定します。数値変換や先頭文字だけの判定ではありません。

| 環境値 | 判定 |
|---|---|
| `on`, `1`, `true`, `yes`（大文字小文字不問、前後空白可） | `on` |
| `off`, `0`, `false`, `no`（大文字小文字不問、前後空白可） | `off` |
| 未設定、空文字、空白だけ | run config の `split_engine` を判定 |
| 上記以外（例: `2`, `auto`, `enabled`） | `auto` |

run config 側は真偽値 `true` / `false` もそれぞれ `on` / `off` として扱います。その他の値は、同じ文字列表にない限り `auto` です。したがって CLI の `--split-engine auto` または設定ファイルの `"split_engine": "auto"` は自動選択を意味します。空または空白だけの環境値は「未指定」として設定値へ戻ります。

根拠: `strata_control/split_engine.py:356-369`。

## 有効になる条件

値が `on` または `auto` でも、split engine の適用条件を満たさなければ通常の layer split が使われます。主な条件は Linux、2〜4 枚の同一 make・同一モデル・同一 VRAM 容量のカード、認識するカード世代とモデル形状、必要な GPU memory / RAM、単一 GGUF file set、`--kv int8`（または `--kv` なし）、MTP draft layer と必要な engine package / `draft_vocab_en.bin` が揃うことです。独自 engine 引数・replicas、DFlash2 指定、drafting off も適用を止めます。各条件の拒否理由は `decide()` と `_apply()` に実装されています（`strata_control/split_engine.py:176-247,435-513`）。

`auto` は一般条件に加えて、NVIDIA ではカードが `AUTO_SPLIT_BEATS_DFLASH2`（この revision では sm_86 / sm_120）に含まれる場合に限り選びます。AMD では `AUTO_SPLIT_AMD_ARCHS`、`AUTO_SPLIT_AMD_CARD_COUNTS`、`AUTO_SPLIT_AMD_EXPERT_TYPES` の条件をすべて満たす場合だけ自動選択します。この revision の定数は AMD gfx1201、4 枚、専門家 tensor type が Q4_K / Q5_K / Q5_1 / Q8_0 の範囲です。`on` はこれらの自動選択 gate を迂回しますが、一般条件は残ります。AMD の明示 `on` では未テスト構成を許す設定も加わります（`strata_control/split_engine.py:41-71,377-390,421-424,484-492`）。

`off` は `apply_split_engine()` 冒頭で戻るため、他の条件を調べず split engine 設定を作りません。`auto` の拒否は `Decision.quiet` になり、通常の layer split が静かに続きます。`on` で拒否されると、その理由を含む一行が launch の設定通知に出ます（`strata_control/split_engine.py:435-448`; `strata_cli/launch/runner.py:1630-1682`）。

## 実行時の詳細

環境値は Python の `os.environ` から `mode()` が呼ばれるたびに読み直され、static cache はありません。launch の予測処理（`expected()`）と、run config を確定する `apply_split_engine()` がそれぞれ判定します（`strata_control/split_engine.py:356-374,398-430,435-448`; `strata_cli/launch/runner.py:1521-1549,1619-1637`）。CLI の `--split-engine` は launch settings に入り run config を組み立てる際に `split_engine` を上書きしますが、非空の環境値はその CLI / 保存済み設定より優先します（`strata_cli/launch/cmd.py:108-111,251-252`; `strata_cli/launch/runner.py:533-551`; `strata_control/split_engine.py:361-369`）。

この判定は server が起動する engine の種類を run config に書く前に行われます。split engine の起動自体が失敗した場合、server は config の `split_fallback` に入った通常 engine を起動し、標準出力へ `[strata] The all-cards split engine could not start (...)` を出します。CLI 側は server の metrics に `split_fallback` があると、split engine ログの末尾にある `sfnx:` 行を添えて警告通知を出します（`serve/server.py:9107-9145`; `strata_cli/launch/runner.py:2198-2219`）。

## 根拠

- 候補名の実読み取りと優先順位: `strata_control/split_engine.py:356-369`。
- 実行モードと環境依存の制約: `strata_control/split_engine.py:176-247,377-390,398-430,435-513`。
- CLI 値の受け取りと run config 反映: `strata_cli/launch/cmd.py:108-111,251-252`; `strata_cli/launch/runner.py:533-551,1619-1682`。
- 起動時 fallback と観測可能な警告: `serve/server.py:9107-9145`; `strata_cli/launch/runner.py:2204-2219`。

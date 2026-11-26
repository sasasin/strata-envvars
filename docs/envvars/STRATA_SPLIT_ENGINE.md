# `STRATA_SPLIT_ENGINE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Terminal の `strata launch` が通常の layer split の代わりに all-cards split engine を使うか、その判定モードを上書きする。`strata_control.split_engine.mode()` は既定の `auto`、明示的に要求する `on`、無効化する `off` を返し、`STRATA_SPLIT_ENGINE` は run config の `split_engine` より優先される。実行するかどうかはこの値だけでは決まらず、カード・モデル・メモリ等の判定も通る必要がある（`terminal/strata_control/split_engine.py:435-448,516-530,567-639`）。

CLI の `--split-engine auto|on|off` は launch 設定に保存される。非空の環境値があればそれが CLI/config の設定に優先し、空の環境値なら config の値を使う（`terminal/strata_cli/launch/cmd.py:108-111,260-261`、`terminal/strata_cli/launch/settings.py:139,446-447`、`terminal/strata_control/split_engine.py:435-448`）。

## 値と判定

環境からは `os.environ.get("STRATA_SPLIT_ENGINE")` で取得する。文字列の前後空白を除き、小文字化した値全体を表の文字列と照合する。数値変換や先頭文字だけの判定はしない（`terminal/strata_control/split_engine.py:435-448`）。

| 環境値 | 判定 | 結果 |
| --- | --- | --- |
| 未設定 | run config の `split_engine` を使う | config も未指定なら `auto` |
| 空文字 `""`、空白だけ `"  "` | 未設定と同様に扱う | run config の値へ戻る |
| `on`, `1`, `true`, `yes` | `on` | 利用を要求し、実行不可なら理由を通知 |
| `off`, `0`, `false`, `no` | `off` | all-cards split engine を使わない |
| 上記の大文字・混在大文字（例 `YES`） | trim 後に小文字化 | 対応する値と同じ |
| 前後に空白がある値（例 ` 1 `） | trim 後に照合 | 対応する値と同じ |
| 未知の非空値（例 `trueish`, `0anything`, `2`） | `auto` | 環境値が config より優先したうえで自動判定 |

config 側の boolean `true` / `false` は `on` / `off` になる。config の文字列も同じ対応表で判定し、未対応値は `auto`。環境値が空文字または空白だけの場合だけ config にフォールバックする（`terminal/strata_control/split_engine.py:441-448`）。

## 有効になる条件

有効値でも all-cards split engine が選ばれない場合がある。

- `off` は常に選択を止める。`auto` は自動判定、`on` は自動判定の一部制限を越えて明示要求するモードだが、ハードウェア・モデル等の基本要件を無効化しない（`terminal/strata_control/split_engine.py:191-264,456-469`）。
- `strata launch` の対象が native Strata model family であれば launcher は split engine 判定を呼ばず、環境値の効果はない（`terminal/strata_cli/launch/runner.py:2241-2248`）。
- 基本判定は Linux、または Windows AMD、2〜4 枚、同一 vendor・同一カードモデルと VRAM 容量、NVIDIA は compute capability 7.0 以上、AMD は対応アーキテクチャ、モデル形状・tensor type 対応、必要 VRAM/RAM、テスト済み context 128K 以下等を要求する（`terminal/strata_control/split_engine.py:191-264`）。
- `auto` では追加の適用条件がある。NVIDIA は `AUTO_SPLIT_BEATS_DFLASH2` の対象カードであること、AMD は `AUTO_SPLIT_AMD_EXPERT_TYPES`、`AUTO_SPLIT_AMD_CARD_COUNTS`、`AUTO_SPLIT_AMD_ARCHS` の各条件を満たすこと（定数は同ファイル `:47-55`、判定は `:456-469`）。それ以外は通常の layer split になる。`on` はこれら auto 専用の除外を越えて要求できる。
- `--drafting off`、または `--drafting dflash2` と `auto`/`off` の組合せ、engine 独自 `user_args`、replicas、`--kv` が `int8` 以外の場合は選ばれない。`on` と DFlash2 の組合せでは対応版 engine と DFlash2 pack が必要（`terminal/strata_control/split_engine.py:477-495,576-639`）。
- 実行 engine package、draft layer（DFlash2 を明示選択した `on` の場合を除く）、`draft_vocab_en.bin` が必要。不足時は通常の layer split に戻る（`terminal/strata_control/split_engine.py:616-639`、`terminal/strata_cli/launch/runner.py:2250-2259`）。
- `STRATA_SPLIT_ALLOW_UNTESTED=1` は未テスト構成の基本判定を許容し、AMD で `on` は未テスト architecture も許容する。これは別変数であり、本変数の値判定を変えない（`terminal/strata_cli/launch/runner.py:2265-2266`、`terminal/strata_control/split_engine.py:502-504,601-604`）。

## 実行時の詳細

Terminal launcher は run config を作る際に `apply_split_engine()` を呼び、その中で `SE.mode(cfg)` を参照してから `SE.apply_to_config()` を実行する。Desktop app 側も `strata split-engine apply` から `apply_run_config()` を呼び、同じ `mode()` の判定を使う（`terminal/strata_cli/split_cmd.py:1-5,41-44`、`terminal/strata_control/split_engine.py:712-737`）。`mode()` 自体にキャッシュはなく、デフォルトでは呼び出しごとに現在の `os.environ` を読む。従って各 Control/Terminal プロセスで launch 判定時点に評価され、実行中に環境を変更しても既に書き出した run config の engine 選択は変わらない（`terminal/strata_cli/launch/runner.py:2228-2237,2241-2281`、`terminal/strata_control/split_engine.py:435-448,516-530`）。

同じ Runner の事前計画には `split_expected()` の memoization があるが、実際の launch 適用は別に `apply_split_engine()` から判定する（`terminal/strata_cli/launch/runner.py:2033-2064,2228-2231`）。この関数は主に app/Terminal の drafting 計画に使われ、環境値の永続キャッシュではない。

`auto` で条件不成立なら通常の layer split を無言で維持する。`on` で判定拒否または処理例外があれば理由を一行通知し、launcher は起動自体を止めない。選択時は `Using the all-cards split engine on N cards.` を通知する。split engine の起動が失敗した場合、server は `[strata] The all-cards split engine could not start (...). Starting the normal layer split instead.` を出して fallback config で通常 engine を起動する（`terminal/strata_control/split_engine.py:123-140,516-530,712-737`、`terminal/strata_cli/launch/runner.py:2265-2281`、`terminal/serve/server.py:8788-8825`）。

## 根拠

- 環境値の読み取り・優先順位・値変換: `terminal/strata_control/split_engine.py:435-448`
- 判定モードと自動適用の追加条件: `terminal/strata_control/split_engine.py:191-264,456-469,516-530`
- 実行条件と split config への変換: `terminal/strata_control/split_engine.py:567-639`
- CLI 設定の取り込みと launch 時の適用・通知: `terminal/strata_cli/launch/cmd.py:108-111,260-261`、`terminal/strata_cli/launch/runner.py:2228-2281`
- Desktop app の Control 経由の適用: `terminal/strata_cli/split_cmd.py:1-5,41-44`、`terminal/strata_control/split_engine.py:712-737`
- split 起動失敗時の fallback: `terminal/serve/server.py:8788-8825`

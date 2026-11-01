# `STRATA_FOUR_CARD_PROFILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

4 枚の AMD Radeon AI PRO R9700（各 28 GB 以上）で Qwen3.8 系 IQ3_S を使うとき、Strata の setup と `strata launch` が serving profile を推奨値として実行設定へ補います。`STRATA_FOUR_CARD_PROFILE` はこの profile の適用を止めるための opt-out です。値を指定して profile を強制する機能ではありません。

profile が適用されると、未選択の設定へ layer split `13,26,39`、`--prefill 2048`、`STRATA_QSA_SLOTS=1`、`STRATA_BATCH_SELF_COMMIT=1`、`STRATA_SLOT_COPY_DIRECT=1` を補います。`parallel` が指定されていなければ 32、さらに `--batch` / `--slots` も指定されていなければ `--batch-groups 4` を補います。既存の設定や利用者の指定を優先します（`strata_control/amd_four_card.py:64-91`）。

## 値と判定

`disabled()` が呼ばれるたびに `os.environ.get("STRATA_FOUR_CARD_PROFILE", "")` を読み、文字列化して前後の空白を除き、小文字化した値を完全一致で比較します（`strata_control/amd_four_card.py:34-38`）。

| 環境値 | 結果 |
|---|---|
| 未設定または空文字 | 環境変数では無効化しない。条件を満たせば profile は適用候補になる |
| `0`, `off`, `no`, `false` | profile を無効化する |
| 上記の前後に空白がある値、大文字・小文字違い | trim / 小文字化後に一致すれば無効化する。例: ` OFF ` |
| その他すべての文字列 | 無効化しない。例: `1`, `true`, `yes`, `2`, `falseish` |

数値変換や真偽値 parse はありません。空文字や `1` は profile を強制せず、ハードウェア等の適用条件を満たさなければ何も起きません。環境値が無効化指定でなくても、run config の `four_card_profile` が Python の `False`（JSON の `false`）なら無効です。環境値を `1` にしても config の `false` を覆しません。逆に config が `true` でも環境値が無効化値なら止まります（`strata_control/amd_four_card.py:34-38,58-61`）。CLI にこの環境変数より優先する専用の強制指定はありません。

## 有効になる条件

無効化されておらず、次の条件をすべて満たす必要があります（`strata_control/amd_four_card.py:41-61`）。

- 選択された GPU がちょうど 4 枚で、報告名が全カード同一かつ空白除去・大文字化後に `R9700` を含み、各カードの vendor が `amd`（省略または空欄時も `amd` 扱い）で、各 VRAM が 28.0 GB 以上。
- backend が `hip`（省略時の既定も `hip`）。
- `model_name` と引数を連結し、小文字化して `-` と `.` を `_` にした文字列に `qwen3_8` と `iq3_s` の両方を含む。
- 引数に `--peer-device` がなく、`replicas` が truthy でなく、`arch` が `deepseek41` でない。

`setup.py` 側ではさらに HIP backend、layer split が未指定または `auto`、replica profile が適用されていないことが呼び出し条件です（`setup.py:10349-10370`）。launcher 側では設定の `gpu` が 4 要素の list であり、その ID に一致する usable GPU を catalog から選べることが呼び出し条件です（`strata_cli/launch/runner.py:1457-1474`）。helper の共通条件もその後に適用されます。

## 実行時の詳細

環境変数は module import 時に固定されず、`apply()` が `applies()` を評価するたびに読み直されます。setup の選択確定時に一度適用されるほか、launcher は `build_config()` のたびに適用します（`setup.py:10363-10370`; `strata_cli/launch/runner.py:1438-1474`）。したがって、同一プロセス内でも次の呼び出し前に環境を変更すれば判定に反映されます。

profile 自体の適用は run config を更新する処理です。環境変数が未設定で有効条件を満たす場合も自動適用されます。既存の `layer_split` や CLI 引数 `--layer-split` が `auto` 以外なら split を変えません。`--prefill auto` だけは setup が書いた既定として `2048` に置き換え、`auto:...` など他の値は保持します。既存の batch switch 環境変数がプロセス環境にあれば profile は config に値を追加せず、config 内に値があれば `setdefault` で保持します。`parallel` が明示されている場合、または `--batch` / `--slots` がある場合は profile が `parallel` と `--batch-groups` を追加しません（`strata_control/amd_four_card.py:70-91`）。

setup は profile の返した説明行を `ok()` で表示します。適用できない条件では行を返さず、env 値だけを理由とするログは出しません。適用例の行には layer split や 32 requests / 4 groups の案内が含まれます。setup 内の例外は `(the four-card profile was not applied: ...)` として通知されます（`setup.py:10363-10370`）。launcher は返された説明があると model event に `Four ... cards: ...` を出し、例外は捕捉して起動を続けます（`strata_cli/launch/runner.py:1457-1474`）。無効化値や非該当ハードウェア自体によってプロセス終了や警告が発生する経路はありません。

launcher がサーバー用 engine 環境を作る際は親プロセスの `os.environ` を複製し、config の `env` を上書き適用します（`serve/server.py:3747-3764`）。この環境変数名の直接読み取りは `strata_control/amd_four_card.py:36` のみであり、engine 側の読み取りは確認できません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:806`。
- 値判定、適用条件、設定値の補完: `strata_control/amd_four_card.py:23-91`。
- setup 呼び出しと例外通知: `setup.py:10363-10370`。
- launcher 呼び出しと通知: `strata_cli/launch/runner.py:1438-1474`。
- engine 環境の構築: `serve/server.py:3747-3764`。
- 文書上の profile 条件・設定と測定結果: `docs/BATCHING.md:565-593`。同資料は 4 枚の R9700、各 28 GB 以上、Qwen3.8 IQ3_S 向け profile と設定値を記載しています。そこにある性能値は同節記載の測定条件に限られ、本調査で再測定していません。

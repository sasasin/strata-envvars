# `STRATA_TIMESKIP_DEADLINE_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Time-skip の任意の Harness revision command `integrations/harness/revise_once.py` において、1 回の agent turn に許す wall-clock 秒数を指定します。これは Strata engine や `strata timeskip` 本体の実行期限ではありません。Time-skip の `--revise-command` にこのスクリプトを指定した場合だけ関係します。スクリプトの説明と使用例は `integrations/harness/revise_once.py:1-23` にあります。

## 値と判定

スクリプトは argparse の `--deadline` の既定値を作るとき、`float(os.environ.get("STRATA_TIMESKIP_DEADLINE_S", 240.0))` を評価します（`integrations/harness/revise_once.py:53-55,70-82`）。

| 環境値 | 結果 |
|---|---|
| 未設定 | `240.0` 秒を既定値にする |
| 空文字 | `float("")` が `ValueError` となる。補完値への fallback はない |
| Python `float()` が解釈できる文字列 | その浮動小数値を秒数として使う |
| 解釈できない文字列 | `ValueError`。値の検査や fallback はない |
| 0 または負数 | 受理される。正数に clamp する処理はない |
| `nan` / `inf` など | `float()` の変換対象であり、有限・正数かの検査はない |

環境値は `main()` が parser に `--deadline` を追加する時点で変換されます。したがって有効な環境値があっても、コマンドラインの `--deadline N` を指定すれば、parse 後の `args.deadline` は CLI の値になります（`integrations/harness/revise_once.py:76-82`）。ただし、環境値自体の `float()` 変換は parser 構築中に先に行われるため、空文字や不正値の場合は CLI の `--deadline` を併記しても変換例外を避けられません。

## 有効になる条件

- `strata timeskip run` で `--revise-command` を指定し、その command として `integrations/harness/revise_once.py` を実行すること。CLI は `--revise-command` の既定値を `None` とし、省略時には revision を実行しません（`strata_cli/cli.py:352-365,1570-1578`）。
- `strata timeskip` は prompt と attempt 番号を `STRATA_TIMESKIP_PROMPT` / `STRATA_TIMESKIP_ATTEMPT` として子 command の環境へ渡します。既存の環境も引き継ぐので、この変数も通常は子へ継承されます（`strata_cli/cli.py:1572-1578`）。
- CLI の `--deadline` は Time-skip 側の引数ではなく、この補助スクリプト自身の引数です。Time-skip の `--attempts` や `--prompt` は deadline 値を設定しません（`strata_cli/cli.py:352-365`）。

## 実行時の詳細

`args.deadline` を用いて、スクリプトは起動時に `deadline = time.time() + args.deadline` を計算します。その後 Harness 起動ログに URL が出るまでの待ち時間を `min(120.0, args.deadline)` に制限し、URL 取得後は `time.time() < deadline` の間、session event を 0.5 秒間隔で確認します（`integrations/harness/revise_once.py:102-115,138-160`）。期限値は環境から parser 既定値として一度読まれ、処理中に環境を再読込するコードはありません。

有効な prompt や Harness 等の前提条件を通過した後、Harness turn が期限内に完了しない場合、stderr に `revise_once: the attempt did not finish within ...s; stopping the Harness and reporting a made attempt` を出して終了コード 1 を返します。`finally` で稼働中の Harness に SIGTERM を送り、8 秒で終了しなければ kill します（`integrations/harness/revise_once.py:138-160,174-187`）。URL の待機期限超過やその他の `BridgeError` も stderr に `revise_once: ...` を出し、終了コード 1 となります（同 `:115-122,168-173`）。

Time-skip CLI は revision command が非ゼロで終了すると `TimeSkipError` として記録します（`strata_cli/cli.py:1577-1583`）。Time-skip の run は例外を `failed` 状態として保存し、通常出力では run 状態を表示し、JSON 出力では `failed` / `interrupted` をエラー終了コード 6 として返します（`strata_control/time_skip.py:480-493`, `strata_cli/cli.py:1585-1601`）。スクリプトが正常終了コード 0 を返した場合も、それは「試行した」という意味であり、改善成功の判定は Time-skip 側の check に委ねられます（`integrations/harness/revise_once.py:164-166`, `docs/work/IMPLEMENTATION_STATUS.md:371-378`）。

## 根拠

- `integrations/harness/revise_once.py:1-23,53-55,70-89,102-115,138-187` — 対象範囲、既定値、変換、期限待ち、ログと終了処理。
- `integrations/harness/_bridge.py:109-122` — Harness URL の期限付き待機と `BridgeError`。
- `strata_cli/cli.py:352-365,1570-1601` — `--revise-command` の任意指定、環境継承、非ゼロ終了の扱い、出力と終了コード。
- `strata_control/time_skip.py:480-493` — run 例外を `failed` として保存する処理。
- `docs/work/IMPLEMENTATION_STATUS.md:361-378` — この補助スクリプトの Time-skip 連携の説明。測定値の根拠には使用していません。

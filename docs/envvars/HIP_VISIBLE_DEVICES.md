# `HIP_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査対象リポジトリの作業ツリーは `main`、`origin/main` と同じで、未コミット変更はありません。

## 役割

Strata はこの名前を AMD/HIP engine の子プロセスに設定・継承し、GPU選択を engine に渡します。また、起動前にGPU一覧を作る処理、serve の Monitor が読むカードの対応付け、AMD画像 reader のカード選択でも値を読みます。HIP runtime や driver がこの値を受け取った後にどう列挙・制限するかは、Strata の処理ではないためここでは扱いません。

serve の `child_env` は親プロセスの環境を複製し、全カード Off なら空文字、HIP backend で設定に GPU があれば `hip_visible(cfg)` の番号列を設定します。その後、設定の `env` が同じキーを指定すれば上書きします。自動選択の条件を満たす場合は `strata-device --list-devices` の結果から作った番号列を設定します（`terminal/serve/server.py:3707-3720, 3832-3860, 3870-3925`）。`--gpu LIST` を渡された engine は初期 GPU 呼び出しより前に同名の変数を読み、CLI 値を設定します（`engine/src/program/generate.cpp:3776-3797`）。

## 値と判定

変数値そのものを Strata が共通形式で検証するわけではありません。どの値が有効かは、参照する Strata の処理ごとに異なります。

| Strata の処理 | unset | 空文字・空白 | 設定値の扱い |
|---|---|---|---|
| AMD GPU一覧の可視カード判定 | 制限なしとして `None`。`ROCR_VISIBLE_DEVICES` があれば先にそちらを判定 | 空白だけなら可視カードなしの `[]` | `ROCR_VISIBLE_DEVICES` の後に HIP 値を適用。各カンマ区切り要素の前後空白を除き、整数として読める ordinal を順に対応付ける。負数または一覧範囲外で走査を止め、それ以前の要素を返す。非数値要素や UUID では対応付け不能の `None` となり、この処理は全カードを残す（`terminal/strata_control/gpu_roles.py:466-510`）。 |
| serve Monitor のカード対応付け | 数値の可視順を復元できず、設定済み GPU がなければ GPU 0 | 無効。空白、空要素、空文字は受理されない | ASCII数字 1〜5 桁をカンマで最大16個、値は 0〜65535、重複なしの場合だけ順序として受理。空白、符号、UUID、範囲外、重複は無効として空リスト扱い（`terminal/serve/server_parts/engines.py:497-519`）。 |
| AMD画像 reader の iGPU 回避 | 空文字相当として扱う | 有効な ordinal はなし | カンマ区切りを trim し、数字だけの要素を ordinal として読む。2個以上あり、既知の AMD GPU 構成に iGPU と独立メモリの GPU が両方ある場合だけ、最後の独立メモリ GPU を reader 用に選ぶ（`terminal/serve/server.py:3978-4012`）。 |
| engine の `--gpu LIST` 処理 | `getenv` は null。警告しない | `prev[0]` が NUL なので警告しない | 現在値が空でなく、CLI 引数全体と異なる場合だけ、環境値を示す警告を出す。値の数値解析はこの箇所ではせず、CLI 引数の文字列をそのまま環境に設定する（`engine/src/program/generate.cpp:3779-3796`）。 |

serve の自動 HIP 選択では、`env.get("HIP_VISIBLE_DEVICES")` が真なら既存値を保ちます。したがって unset と空文字はどちらも自動プローブを妨げませんが、空文字が GPU一覧判定で「空の可視一覧」となる点は別です。空白文字列は Python では真なので自動プローブを止めます。併せて `ROCR_VISIBLE_DEVICES` が真の場合も自動選択しません（`terminal/serve/server.py:3832-3838`）。

## 有効になる条件

- `child_env` が HIP backend 用として値を組み立てるのは serve が Strata engine を起動するときです。設定上の GPU または `hip_ordinal` があれば `hip_visible(cfg)` が番号列を作ります。Windows の `hip_ordinal` は、GPUが1枚以下の場合に設定上の `gpu` より優先します（`terminal/serve/server.py:3707-3720, 3870-3889`）。
- 設定の `env` は serve が計算した値を上書きします。さらに、HIP engine 起動時に `--gpu LIST` があれば engine 側がその値を上書きします。環境値が空、または CLI と同一なら engine の上書き警告は出ません（`terminal/serve/server.py:3890-3891`; `engine/src/program/generate.cpp:3779-3796`）。
- 自動選択は backend が `hip` で、設定に GPU指定・全カード Off・空でない `hip_ordinal` がなく、HIP と ROCR の環境値も空である場合に限ります。実行ファイルが参照用でないこと、隣に `strata-device` が存在すること、60秒以内に probe が成功して終了コード0を返すことも必要です。probe 不在・例外・非ゼロ終了では値を自動設定せず、既存環境を残します（`terminal/serve/server.py:3832-3860`）。
- 自動選択では、Strata の `strata-device` 出力から読んだカードのうち `cannot run` のないものを候補にします。実行可能な非統合GPUがあれば統合GPUを候補から外し、最初のカードが候補なら順序を保ち、そうでなければ VRAM が最大のカード（同値なら小さい番号）を選びます。使えるカードがない場合は `SystemExit` になります（`terminal/serve/server_parts/engines.py:1020-1067`; `terminal/serve/server.py:3852-3855`）。
- updater の HIP engine smoke test も、HIP/ROCR の値が空で、実行可能な非統合GPUを除外する必要があるときだけ、`--version` 子プロセスの `HIP_VISIBLE_DEVICES` を設定します。値がある場合、probe がない場合、または失敗した場合は既存の試験環境で続けます（`terminal/strata_control/updater.py:961-985, 1013-1027`）。
- `strata launch` のカード役割表示と split engine の候補一覧は環境値を読み、カードを絞ります。AMDでは `ROCR_VISIBLE_DEVICES` を先に適用し、その結果を ordinal の基準として `HIP_VISIBLE_DEVICES` を続けて適用します。役割表示では明示的に指定したカードは `keep` に含まれ、環境フィルターで除外されません（`terminal/strata_control/gpu_roles.py:485-518`; `terminal/strata_control/split_engine.py:396-405`; `terminal/strata_cli/launch/cmd.py:425-442`）。
- 画像生成 helper は `backend == "hip"` かつ config に `gpu` がある場合にこの変数を設定し、その後 config の `env` が上書きします。実行時は `image_env` の結果を画像 CLI の subprocess に渡します（`terminal/serve/images.py:177-196, 468`）。
- `strata-vision` と `strata-vision-own` は `--gpu` を指定しない場合、Windows では `_putenv_s`、それ以外では `setenv(..., 1)` で値を `-1` に設定します。Strata が両 reader のプロセス内環境を書き換える処理です（`terminal/tools/vision/strata_vision.cpp:97-107`; `terminal/tools/vision/own/own_main.cpp:31-41`）。

## 実行時の詳細

`child_env` は呼び出しごとに `os.environ` を複製して子プロセス用辞書を作り、その辞書を engine に渡します。したがって親環境の変更は、その後に作られる環境辞書には反映されますが、既に起動した子プロセスの環境はこの関数から更新されません。関数内に `HIP_VISIBLE_DEVICES` の static cache はありません（`terminal/serve/server.py:3870-3925, 8870-8878`）。replica、split-serving の各 engine も、それぞれの設定から `child_env` を作って起動します（`terminal/serve/server.py:8313-8336, 8394-8403`）。

serve の自動 probe は、組み立てた子環境をそのまま `strata-device --list-devices` に渡し、得られた結果に応じて同じ辞書を書き換えます（`terminal/serve/server.py:3842-3860, 3922-3925`）。設定済みの数値列は Profile の `env` が後から上書きできます。serve は `--gpu` を含む engine 引数と環境辞書を別々に渡し、engine の `main` は `--gpu` 引数がある場合だけ起動時に対象環境値を一度読みます。変数の再読み取りや Strata 側の cache はここにはありません（`engine/src/program/generate.cpp:3776-3797`）。

Monitor は設定済み `gpu_list(cfg)` があればその先頭カードを優先し、設定がない場合に限り `HIP_VISIBLE_DEVICES` から厳格に復元できる先頭 ordinal を使います。曖昧・不正な値では GPU 0 に戻ります（`terminal/serve/server_parts/engines.py:497-519`; `terminal/serve/server.py:9135-9155`）。

## ログと測定値

- serve の自動選択でカードを選んだ場合: `[strata] automatic GPU choice: GPU {index} ({name}, {arch}); the engine skips cards it has no code for and integrated chips while a card of its own can run`（`terminal/serve/server.py:3856-3859`）。
- 自動選択 probe が成功し、カードは見つかったものの Strata engine が実行できるカードが1枚もない場合、serve は `[strata] none of this computer's graphics cards has code in this Strata engine ...` の行を `SystemExit` の理由にします。probe 不在・失敗・カード一覧が空の場合はこのエラーにはならず、値を設定しません（`terminal/serve/server.py:3842-3855`; `terminal/serve/server_parts/engines.py:1042-1060`）。
- `--gpu LIST` と環境の値が異なり、環境側が空でない場合: `warning: --gpu {LIST} overrides HIP_VISIBLE_DEVICES={previous} from the environment`。CUDA build では同じコードが `CUDA_VISIBLE_DEVICES` を対象にするため、この HIP 警告は `STRATA_USE_HIP` または `STRATA_HIP_GFX906` build の場合です（`engine/src/program/generate.cpp:3781-3795`）。
- iGPU を含む複数カード構成で reader 用カードを変えた場合: `[strata] the picture reader runs on GPU {N}, not on the built-in graphics (GPU {indices}) that draws the desktop; "vision": {"cuda_device": N} chooses another card`（`terminal/serve/server.py:3983-4012`）。
- 測定値は記載しません。Strata の該当資料にこの変数による性能測定条件はありません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:387`。この名前は Strata 内で実際に読み取り・設定・転送されているため、索引との食い違いはありません。
- serve の環境生成・自動選択: `terminal/serve/server.py:3707-3720, 3832-3860, 3870-3925`。
- engine の `--gpu` による読み取り・上書き: `engine/src/program/generate.cpp:3776-3797`。
- 環境を使ったカード列挙・役割表示・split: `terminal/strata_control/gpu_roles.py:466-518`; `terminal/strata_control/split_engine.py:396-405`; `terminal/strata_cli/launch/cmd.py:425-442`。
- Monitor と画像 reader: `terminal/serve/server_parts/engines.py:497-519`; `terminal/serve/server.py:3978-4012`。
- updater smoke test と画像 CLI: `terminal/strata_control/updater.py:961-985, 1013-1027`; `terminal/serve/images.py:177-196, 468`。
- vision helper の環境設定: `terminal/tools/vision/strata_vision.cpp:97-107`; `terminal/tools/vision/own/own_main.cpp:31-41`。
- Strata の設計資料では、設定・環境がある場合の自動選択スキップを説明しています（`docs/AMD_HIP.md:67-69`）。現行ソースでは serve の明示 GPU 選択を ambient env より先に反映し、さらに profile の `env` を後から適用するため、細かな優先順位は上記ソースを根拠にしました。

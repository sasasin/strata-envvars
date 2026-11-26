# `GPUS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`GPUS` は Strata の Docker entrypoint が読む設定で、コンテナ起動時に `strata launch --gpu <値>` へ GPU 番号を渡す。Strata engine や通常の Terminal 起動処理が `GPUS` を直接読む実装は見つからなかった。Compose の NVIDIA 例も `GPUS` を任意指定として示している（`tools/docker/entrypoint.sh:20,226-228`、`tools/docker/compose/docker-compose.nvidia.yml:16-25`）。

`GPUS` が空または `all` / `ALL` の場合、entrypoint は `--gpu` を付けない。これは既存の選択を消して全カード指定にする処理ではない。`strata launch` は preset の設定を読み込むため、保存済み GPU 選択があれば維持され、選択がなければその後の launch/setup の選択規則に委ねられる（`terminal/strata_cli/launch/cmd.py:215-220`、`terminal/strata_cli/launch/runner.py:506-535`）。

## 値と判定

entrypoint は `gpus="${GPUS:-${GPU:-}}"` として値を決める。シェルの `:-` 展開により、`GPUS` が未設定または空文字なら旧名 `GPU` の値を使い、`GPUS` が非空なら `GPU` より優先する。値の判定は大文字小文字を区別し、`""`・`all`・`ALL` だけが `--gpu` を省く分岐である（`tools/docker/entrypoint.sh:226-228`）。

| 条件 | `GPUS` の値 | entrypoint の結果 |
|---|---|---|
| unset / 空文字 | `GPU` も unset / 空 | `--gpu` なし。preset の既存選択または launch の既定選択に委ねる |
| unset / 空文字 | `GPU=0` など非空 | `GPU` の値を `--gpu` に渡す |
| 非空 | `all` または `ALL` | `--gpu` なし。`GPU` の値は使わない |
| 非空 | `0`、`0,1` など | 値全体を一つの `--gpu` 引数として渡す |
| 非空 | `All`、` all ` など | 省略分岐に一致せず、そのまま `--gpu` に渡す |

launch 側の `_gpus()` は値中の ASCII 空白を除き、カンマで分割し、空要素を飛ばして残りを Python `int()` に変換する。従って `0, 1` は `[0, 1]`、`0,` は `[0]`、`,` は空リストになる。符号付き整数など `int()` が受け付ける整数表記も変換され、`All` のような文字列は `ValueError` となる。独自の範囲・重複チェックはこの変換関数にはない。存在しない GPU 番号や負数が後続経路でどう扱われるかは、この変換箇所だけからは一律に断定できない（`terminal/strata_cli/launch/cmd.py:206-212`）。

空値・`all`・`ALL` 以外の値を `--gpu` に渡し、`GPU_ROLES` も非空なら entrypoint は起動前に終了コード 2 で拒否する。`GPU_ROLES` があるとき `gpus` が空 / `all` / `ALL` なら競合判定を通り `--gpu-roles` を使う（`tools/docker/entrypoint.sh:243-246`）。CLI 側も `--gpu` と `--gpu-roles` の同時指定を拒否し、`--gpu` を受けると roles 設定を解除する（`terminal/strata_cli/launch/cmd.py:262-273`）。

## 有効になる条件

- Docker entrypoint の通常起動経路で有効。`docker run IMAGE strata ...` のように別コマンドを指定した場合は entrypoint が先に `exec` するため、この値処理に入らない（`tools/docker/entrypoint.sh:68-71`）。
- `GPUS` が非空かつ `all` / `ALL` 以外なら `--gpu` に渡される。launch の preset に他の値があっても CLI 指定が重ねられ、`settings_from_args()` は `s.gpus` を設定する（`terminal/strata_cli/launch/cmd.py:215-220,262-266`）。
- 既存 `/data/install/strata-*.json` の `gpu` と要求値（空白除去後）が異なる場合、その設定ファイルを削除する。entrypoint の説明ではモデルファイルは保持したまま作り直す経路である。同じ指定なら削除しない（`tools/docker/entrypoint.sh:229-239`）。
- `GPUS` が未設定 / 空なら `GPU` が代替入力となる。どちらも空なら `GPUS` による上書きはなく、保存済み設定が優先される場合がある（`tools/docker/entrypoint.sh:226-228`、`terminal/strata_cli/launch/runner.py:506-535`）。
- `GPU_ROLES` と併用できるのは `gpus` が空 / `all` / `ALL` の場合だけで、その場合は roles 指定が `--gpu-roles` として渡る。数値指定と roles 指定の併用は拒否される（`tools/docker/entrypoint.sh:243-246`）。
- OS や engine backend による `GPUS` 自体の分岐は entrypoint にない。番号の意味と利用可能性は後続の launch/setup/backend が扱う。

## 実行時の詳細

entrypoint は実行時に一度だけシェル変数へ展開し、`--gpu` を引数として `strata launch` に渡す。以後の環境変更を再読するコードはこの entrypoint にない。GPU を明示した launch は設定 JSON の `gpu` と `gpus_asked` に反映され、複数カードでは通常の engine に `layer_split=auto` を補う（native EP / Qwen 3.5 MoE 経路を除く）。launch はその run config を保存し、setup に渡す引数にも単一なら `--gpu`、複数なら `--gpus` を設定から生成する（`terminal/strata_cli/launch/runner.py:398-434,1414-1419,2216-2238`）。

名前の完全一致検索では、製品実行経路の読み取りは `tools/docker/entrypoint.sh:226` のみだった。別に研究用 probe `tools/research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-30` が `os.environ.get("GPUS")` を読み、真値ならカンマ区切りを `int` 化して probe 設定の `gpu` に入れ、`SPLIT` も読む。このスクリプトの値処理は専用 probe のものなので、Docker/Terminal の製品設定の規則には適用しない。`terminal/tools/portable_monitor_smoke.py:69` などの表示名やテスト・docs・benchmark 記録の出現は環境から値を読む箇所ではない。

## ログと測定値

- 保存済み GPU 選択が要求値と異なり設定を作り直す場合、entrypoint は `The saved run settings use graphics card '…', GPU/GPUS asks for '…': making them again (model files are kept).` を stdout に出す（`tools/docker/entrypoint.sh:231-238`）。
- `GPU_ROLES` と数値の `GPU` / `GPUS` を併用した場合、`[X] Set GPU_ROLES or GPU / GPUS, not both.` を stderr に出して終了コード 2 となる（`tools/docker/entrypoint.sh:243-246`）。
- 数値に変換できない値は CLI が `strata: '<値>' is not a list of graphics card numbers. Use 0 or 0,1.` を stderr に出して終了コード 2 を返す。entrypoint はその後 `strata launch stopped with code 2 (the lines above say why). ...` と出し、同じコードで終了する（`terminal/strata_cli/launch/cmd.py:206-212,759-764`、`tools/docker/entrypoint.sh:310-316`）。
- 測定値は該当なし。

## 根拠

- `tools/docker/entrypoint.sh:68-71,226-246,268-275,299-317`
- `tools/docker/compose/docker-compose.nvidia.yml:16-25`
- `terminal/strata_cli/launch/cmd.py:206-220,262-273,759-764`
- `terminal/strata_cli/launch/runner.py:398-434,506-535,1414-1419,2216-2238`
- `tools/research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-33`

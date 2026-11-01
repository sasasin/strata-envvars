# `VISION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`VISION` は Strata Docker イメージの標準起動時に、画像を扱う設定を `strata launch --vision` に渡すための環境変数です。Strata の engine や server がこの名前を直接読む箇所は確認できません。読み取りは `docker/entrypoint.sh` にあり、値は起動 CLI 引数に変換されます。

Docker Compose の NVIDIA / AMD / Intel 各定義は `${VISION:-off}` を環境に設定するため、未指定または空の Compose 値は `off` になります。一方、直接 `docker run` して変数を unset または空にすると entrypoint は `--vision` を追加せず、保存済み preset または `strata launch` のモデル・engine 既定に従います。Compose と直接起動ではこの既定の経路が異なります。

## 値と判定

entrypoint は値を ASCII 大文字から小文字へ変換してから、全体一致の `case` で判定します。数値変換や前後空白の trim はしません。

| `VISION` の値（大文字小文字不問） | `--vision` に渡す値 |
|---|---|
| `off`, `no`, `false`, `0` | `off` |
| `on`, `yes`, `true`, `1` | `on` |
| `gpu` | `gpu` |
| `cpu` | `cpu` |
| unset または空文字 | 引数を追加しない |
| 上記以外（例: `maybe`, ` on`, `2`） | stderr に `VISION=<値> is not one of off, on, gpu, cpu.` を出し、終了コード 2 で停止 |

エイリアスは `docker/entrypoint.sh` だけで正規名へ変換されます。変換後の値は `strata_cli/launch/settings.py` の `VISION_MODES`（`off`, `on`, `gpu`, `cpu`）と `strata launch --vision` の選択肢に一致します。

## 有効になる条件

- 通常のコンテナ server 起動経路であること。entrypoint にコマンド引数を渡すと、`strata` コマンドはそのまま実行され、他のコマンドも直接 `exec` されます。この分岐では `VISION` の検証・変換を通りません。
- 変数が unset / 空でないこと。値があるときは正規化した `--vision` 引数が追加され、launch のプリセット指定より今回の起動に渡す CLI 選択として適用されます。設定があるため、entrypoint は preset がすでに存在すれば `--save-preset` も付け、選択を保存します。
- `on` は画像対応モデルと reader が利用可能なときに画像を有効にする指定です。モデルが画像非対応なら launch は警告を出して `off` にします。reader がない場合も、画像を使えない旨の警告経路があります。
- `on` は reader の実行方式を固定しません。Strata setup は GPU メモリに応じて CPU / GPU reader を選びます（NVIDIA / own-path 実装では 23.5 GiB 未満は CPU、それ以外は GPU。HIP は `vision_reader` の選択処理を通ります）。`cpu` / `gpu` は方式の明示指定です。GPU reader がビルド済みか、モデルが画像対応かなどの状態によって実際に画像を読めるかは別途制約されます。

## 実行時の詳細

entrypoint は起動時に一度だけシェル環境を調べます。unset と空文字は `[ -n "${VISION:-}" ]` により同じ扱いです。値がある場合は小文字化・検証し、`set -- "$@" --vision "$v"` で CLI 引数へ追加します。続けて標準起動では `strata launch` を実行します。プロセス稼働中に環境変数を変えても再評価されません。

launch の `--vision` は保存済み preset に対する今回の選択として `settings.vision` に反映されます。launch runner は `on` を setup の `yes` に、`off` を `no` に写して setup を呼び、選択を preset に保存します。`gpu` / `cpu` はそのまま setup に渡されます。設定が未指定なら、preset とモデル・reader の既定判定に委ねられます。

Docker Compose の NVIDIA / AMD / Intel 定義はいずれも `VISION: ${VISION:-off}` です。そのため Compose からは `VISION` が空でも `off` が渡り、標準起動で画像を無効にする明示指定になります。Compose を介さない起動では、この補完はありません。

無効値のときは Strata launch の起動前に stderr の `die` メッセージを出して exit 2 になります。標準起動の launch 自体が非ゼロで終わった場合、entrypoint は `strata launch stopped with code ...` を出してそのコードで container を終了します。値が有効でもモデル非対応や reader 不在なら launch の警告を観測できます。

## 根拠

- `docker/entrypoint.sh:16,190-202` — 変数の説明、unset / 空判定、大小文字変換、受理値、エラー文と exit code、CLI 引数への変換。
- `docker/entrypoint.sh:53-56,242-250,273-290` — 任意コマンド時の分岐、preset 選択と保存、launch 起動および失敗時の終了経路。
- `docker/compose/docker-compose.nvidia.yml:16-22`、`docker/compose/docker-compose.amd.yml:16-21`、`docker/compose/docker-compose.intel.yml:16-21` — Compose が未指定値を `off` に補完してコンテナへ設定する箇所。
- `strata_cli/launch/settings.py:26-28`、`strata_cli/launch/cmd.py:96-99,232-238` — canonical 値と CLI 引数による設定。
- `strata_cli/launch/cmd.py:344-351`、`strata_cli/launch/runner.py:894-898` — モデル非対応・reader 不在時の警告経路。
- `strata_cli/launch/runner.py:868-883,900-913`、`setup.py:3384-3401,4842-4848` — `on` / `off` の setup 向け変換と reader 選択。GPU / CPU の実際の可用性は setup と engine 配布物に依存します。
- `docs/DOCKER.md:110-123,265-275` — Docker 用変数の説明と旧イメージからの対応。現行動作の根拠は上記ソースです。

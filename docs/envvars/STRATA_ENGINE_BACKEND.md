# `STRATA_ENGINE_BACKEND`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata Control がローカル engine component の選択や engine 更新時に使う backend family を指定します。engine の設定ファイルに `"exe": "component:strata-engine"` がある場合、run config の `backend` が有効な family でなければ、この環境変数または GPU 検出結果を使って起動対象 package を選びます。`strata update` では feed から選ぶ backend を指定します。デスクトップ host に同梱された engine package の選別にも使われます。

engine binary 自身がこの名前を読む箇所は見つかりませんでした。ここで説明するのは Control/host が行う選択です。候補一覧にも登録されています（`docs/envvars/000_envvers.md:755`）。

## 値と判定

Python の共通判定は `strata_control/engine_component.py:439-456` の `split_backend()` / `detect_backend()` です。値を文字列化し、前後の空白を除き、小文字化します。文字列全体の値比較であり、真偽値や数値への変換はしません。

| 値 | Control の判定 |
|---|---|
| 未設定、空文字、空白だけ | backend の明示指定なし。OS/GPU 検出へ進む |
| `cuda`, `hip`, `sycl`, `metal`, `cpu` | `BACKEND_MATRIX` にある family として指定を採用 |
| `hip-<variant>`（例: `hip-rdna2`） | family は `hip`、variant は接尾辞。更新時には variant 指定としても保持されるが、通常の engine 起動判定は family `hip` のみを使う |
| その他（`0`, `false`, `vulkan` など） | 無効値。`ComponentProblem` を送出し、GPU 検出へは fallback しない |

大文字小文字と前後空白は正規化されます（例: ` HIP ` → `hip`）。`hip-` の接尾辞は空でない必要があります。任意の backend 名を受け付けるものではなく、family は `strata_control/targets.py:23-29` の対応表に限定されます。OS ごとの対応可否も別途適用されます（同ファイル `:31-53`）。

## 有効になる条件

- **Engine 起動**: `component:strata-engine` 参照が使われ、run config の `backend` が `BACKEND_MATRIX` の有効な family でない場合に環境変数が選択に使われます。有効な config backend があればそちらが優先されます（`strata_control/engine_component.py:1007-1016`）。コンポーネントを使わず engine の実行ファイルを直接指定する config では、この resolver を通りません。
- **明示的な CLI 指定**: `strata components engine --backend ...` は検出結果を上書きします（`strata_cli/cli.py:132-138,2014-2028`）。`strata update --backend ...` は環境変数を読んだ後に backend と variant を上書きし、`backend_source` を `requested` にします（`strata_cli/update_cmd.py:194-206`）。この明示指定は更新時の GPU make guard を通過します（`strata_control/updater.py:546-558`）。
- **OS / backend**: 自動検出で macOS は `metal` を返します。その他は Windows の display adapter を先に見てから `nvidia-smi` / `rocminfo`（Windows は `hipInfo`）/ `sycl-ls`、最後に PCI vendor を調べます。検出できない場合、engine 起動 resolver は `cpu` を選びます（`strata_control/engine_component.py:448-491,918-924`）。ただし指定 backend に対応する platform/package がなければ起動対象にはなりません（同 `:931-986`、`strata_control/targets.py:23-53`）。
- **Updater の variant**: `hip-<variant>` は `detect_hardware()` が family と variant に分け、`hip` として backend 検出しながら `variant_wanted` に suffix を保存します。AMD の gfx が特定できず複数 HIP variant が候補になる場合、要求 variant が最初の選択根拠になります（`strata_control/updater.py:255-275`; `strata_control/feed.py:468-495`）。
- **同梱 package の host 経路**: `apps/host/server/bundled-engine.mjs:107-125` は値を trim/lowercase し、`cuda` / `hip` / `sycl` のみを受け付けます。空値なら adapter/driver/PCI 検出へ進みますが、その他の非空値は空候補 `[]` を返し、自動検出しません。Python 側と違い、ここでは `metal` / `cpu` / `hip-<variant>` は有効な強制値ではありません。同梱 package 選別はこの結果を使います（同 `:168-190`）。

## 実行時の詳細

Python 側に値の parse 結果を保持する static cache はありません。`detect_backend()` の呼び出しごとに `os.environ`（または明示的に渡された mapping）から値を読みます。engine 起動では `runtime._engine_preflight()` が component 参照を検出して `expand()` を呼び、`expand()` は有効な config backend を優先し、それ以外の場合 `resolve()` が環境変数を判定します（`strata_control/runtime.py:465-481`; `strata_control/engine_component.py:909-924,1007-1016`）。更新では `strata update` の hardware 検出時に読み、後続の package 選択・make guard にその判定を渡します（`strata_cli/update_cmd.py:194-206`; `strata_control/updater.py:255-275,546-570`）。

値が無効な場合、Python の `detect_backend()` は `STRATA_ENGINE_BACKEND=<正規化後の値> is not one of ...` という `ComponentProblem` を送出します。`strata components engine` はエラーを表示して終了コード 2 を返す経路があります（`strata_control/engine_component.py:448-456`; `strata_cli/cli.py:2014-2023`）。有効値でも一致する component がない、platform/backend が非対応、整合性確認に失敗する場合、engine resolver は理由を含む `EngineMissing` / `EngineIntegrityError` を返し、start preflight は開始前に拒否します（`strata_control/engine_component.py:931-986`; `strata_control/runtime.py:465-481`）。`strata components engine` は利用可能な engine がない場合に終了コード 5 を返します（`strata_cli/cli.py:2014-2025`）。

## 根拠

- `strata_control/engine_component.py:439-456` — 値の正規化、`hip-variant` の分割、未知値のエラー、自動検出の入口。
- `strata_control/engine_component.py:448-491,909-986` — backend 自動検出、未検出時の CPU fallback、指定 backend に合う engine package の選択と失敗理由。
- `strata_control/engine_component.py:1007-1016`; `strata_control/runtime.py:465-481` — run config の component 参照と config backend の優先順位、起動前 preflight。
- `strata_control/updater.py:255-275,546-570`; `strata_control/feed.py:468-495`; `strata_cli/update_cmd.py:194-206` — 更新時の環境値・variant の利用、`--backend` 上書き、make guard。
- `apps/host/server/bundled-engine.mjs:101-125,168-190` — host の異なる値判定と同梱 package 選別。
- `strata_control/targets.py:20-53`; `packaging/README.md:103-119` — 対応 OS/backend、起動時の component 解決と利用不可時の説明。

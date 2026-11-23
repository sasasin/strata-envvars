# `STRATA_ENGINE_BACKEND`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal の Control はこの変数で backend（`cpu` / `cuda` / `hip` / `metal` / `sycl`）を明示できます。`strata launch` の実行先エンジン判定、モデルの GPU 適合先判定、更新対象エンジンの選択に使います。デスクトップの host server は同梱エンジンを導入するとき、この変数で候補 GPU backend を絞ります。エンジン本体がこの名前を読む箇所は確認できません。Control と host server の処理に対する指定です。`terminal/strata_control/engine_component.py:542-550`、`terminal/strata_cli/launch/catalog.py:433-445`、`terminal/strata_control/updater.py:316-336`、`terminal/strata_control/targets.py:25-31`、`app/host/server/bundled-engine.mjs:107-125,168-190`

## 値と判定

| 読み取り経路 | 未設定・空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Terminal Control (`split_backend`) | `environ.get(..., "")` の空文字となり、自動検出へ進む | 前後空白を除いて小文字化した backend `cpu` / `cuda` / `hip` / `metal` / `sycl`。別名 `nvidia`→`cuda`、`amd`→`hip`、`intel` / `arc`→`sycl`。`hip-<任意の非空 suffix>` は backend `hip` と suffix に分割される | 別名・backend 名でない値は `ComponentProblem`。`hip-` は suffix が空なので無効。大文字は小文字化され、前後空白は除かれる。内部空白や値全体の形式検査は別途行わない |
| 同梱エンジン選択 (`gpuBackendsHere`) | `null` または空文字は空指定となり、GPU 検出へ進む | `trim().toLowerCase()` 後に完全一致する `cuda` / `hip` / `sycl` | それ以外（例 `amd`, `hip-rdna2`, `false`, `cpu`, `metal`）は `[]` を返す。非空の不受理値では自動検出にも進まない。大文字・前後空白は正規化される |

Terminal 側は `str(value or "").strip().lower()` で値を正規化し、backend matrix のキーまたは別名と文字列全体で照合します。backend matrix には `cpu`, `cuda`, `hip`, `metal`, `sycl` が含まれます。`getenv` の設定有無ではなく値を解析します。空文字、空白だけの値、未設定はいずれも空として扱われます。`hip-` 以降の suffix は空でないことだけを確認し、形式を検証しません。`detect_backend` は suffix を backend `hip` に変換して使います。一方、更新用 `detect_hardware` は suffix を `variant_wanted` に残し、候補パッケージ選択に渡します。`terminal/strata_control/engine_component.py:490-500,542-550`、`terminal/strata_control/targets.py:25-31`、`terminal/strata_control/updater.py:316-336`

## 有効になる条件

- Terminal で backend 選択を行う経路で参照されます。設定が空なら、保存済み選択、macOS の `metal`、Windows の表示アダプター、利用可能な GPU probe、PCI vendor 検出の順に判定します。したがって環境値がある場合は保存済み選択や自動検出より優先されます。`terminal/strata_control/engine_component.py:551-591`
- `strata launch --backend nvidia|amd|intel` は値を正規化してこの変数をそのプロセス内に設定し、設定ファイルにも保存します。`--backend auto` は保存済み選択を消し、プロセス環境からもこの変数を削除します。CLI 指定はプロセス開始時の環境値に優先します。`--plan` では保存・削除の設定ファイル変更をしません。`terminal/strata_cli/launch/cmd.py:817-837`
- 保存済み backend は環境値がないときだけ参照されます。ただし、その選択先の GPU make が現在の PC にない場合は無視されます。`terminal/strata_control/engine_component.py:513-524,551-553`
- `strata update --backend ...` が指定された場合は、CLI 値から一時環境を作って hardware 判定するため、継承した環境値より CLI 値が優先します。`hip-rx9070` のような指定は family `hip` と variant `rx9070` に分けられます。`terminal/strata_cli/update_cmd.py:283-300,314-321`
- デスクトップの同梱エンジン導入は host Control が存在し、`STRATA_NO_BUNDLED_ENGINE` が設定されておらず、bundle に候補がある場合に実行されます。この変数が `cuda` / `hip` / `sycl` なら指定した backend 以外の GPU package を除外します。未設定・空なら GPU vendor 検出へ進みます。非空の不受理値では関数が `[]` を返してそのまま続くため、GPU vendor 検出も backend による絞り込みも行いません。`app/host/server/index.mjs:165-176`、`app/host/server/bundled-engine.mjs:107-125,168-190`
- build macro による分岐はありません。Python Control と Node host server のそれぞれが実行時に読みます。`terminal/strata_control/engine_component.py:542-550`、`app/host/server/bundled-engine.mjs:107-109`

## 実行時の詳細

Terminal の `detect_backend(environ=None)` は引数がなければ呼び出し時点の `os.environ` を使い、環境値を関数ローカルで解析します。static cache はありません。`resolve` に明示 backend が渡された場合は環境値の判定を飛ばし、その backend を使います。設定された run config の `backend` が backend matrix のキーなら `config_executable` がそれを明示値として渡すため、環境値より優先します。明示値がないときは `detect_backend` の結果を使い、何も検出されなければ CPU engine を対象にします。`terminal/strata_control/engine_component.py:542-550,1136-1155,1249-1263`

`strata launch` が環境値を設定した場合、同じプロセスの後続判定に使われ、起動するプロセス環境にも引き継がれます。Python Control 自体はプロセス環境を再参照するため、起動後に値を変えた場合も後続呼び出しでは新しい値が使われます。`terminal/strata_cli/launch/cmd.py:817-837`、`terminal/strata_control/runtime.py:1056-1074`

更新経路では `detect_hardware` が呼び出し時の環境を受け取り、backend と必要なら HIP variant を選択情報に記録します。環境値が `hip-<suffix>` の場合、backend 検出用の一時環境では family `hip` に置き換え、suffix は `variant_wanted` として別に保持します。`terminal/strata_control/updater.py:316-336`

デスクトップ host server は同梱エンジン導入時に `gpuBackendsHere()` を呼びます。関数は呼び出しごとに渡された環境（通常は `process.env`）を参照し、キャッシュしません。`STRATA_ENGINE_BACKEND` が `cuda` / `hip` / `sycl` なら package の backend を限定し、候補に指定 backend が一つもなければ `wrong-make` 結果を返します。未設定・空の場合は vendor 検出を試します。非空の不受理値では自動 vendor 検出を行いません。`app/host/server/bundled-engine.mjs:107-125,168-190`

## ログと測定値

有効値を選んだことだけを理由に出すログはありません。Terminal 側で未対応値を判定すると、`ComponentProblem` の文言は ``STRATA_ENGINE_BACKEND='<値>' is not one of cpu, cuda, hip, metal, sycl`` です（列挙順は `sorted(BACKEND_MATRIX)` に依存）。`strata launch` の外側は `ValueError` を捕捉し、通常出力では `strata: <文言>` を stderr に出して終了コード 2、JSON 出力では error message として返します。engine status の場合は例外を捕捉して backend source にエラー文言を記録します。`terminal/strata_control/engine_component.py:542-550,1265-1279`、`terminal/strata_control/targets.py:25-31`、`terminal/strata_cli/launch/cmd.py:759-764,1009-1012`

デスクトップ側の backend 不一致は `wrong-make` の結果になり、`app/host/server/index.mjs:174-176` がその notice を `console.log` に出します。Strata の資料に、この変数による性能測定値はありません。

## 根拠

- `terminal/strata_control/engine_component.py:490-500,542-591` — Terminal の値変換、優先順位、自動検出。
- `terminal/strata_control/engine_component.py:1136-1175,1265-1285` — 明示 backend と検出結果による engine 選択・status。
- `terminal/strata_cli/launch/cmd.py:817-837` — `--backend` による環境の上書き・削除と保存。
- `terminal/strata_cli/launch/catalog.py:433-445` — 環境指定をモデル向け GPU vendor 選択へ反映。
- `terminal/strata_control/updater.py:316-336`、`terminal/strata_cli/update_cmd.py:283-321` — 更新対象 backend / variant の決定と CLI 優先。
- `terminal/strata_control/runtime.py:1056-1074` — server 子プロセスへの環境引き継ぎ。
- `app/host/server/bundled-engine.mjs:101-133,168-190`、`app/host/server/index.mjs:165-176` — 同梱 package 選択と不一致 notice。

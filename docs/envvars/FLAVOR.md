# `FLAVOR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`FLAVOR` は手動起動の `Docker images` GitHub Actions workflow が `image` job の matrix 値を一つ受け取り、同じ値を `tools/docker/publish.sh --flavors` に渡す step 環境変数です。通常の Strata / Terminal / engine 起動時に読む設定ではありません（`.github/workflows/docker-images.yml:12-13,70-81,97-104`）。

その値は release に含まれる Linux x86-64 engine package の選択に使われ、対応する Docker image の tag にも残ります。package の backend に対応する `cuda` / `hip` / `sycl` は `fetch-engines.py` が出力し、`build.sh` に `--flavor` として渡します。Dockerfile はその build option から渡された Docker build argument `FLAVOR` に応じて runtime image に追加する OS package 群を選びます。workflow の `FLAVOR` と Dockerfile の `ARG FLAVOR` は別段階の値で、実行時設定として container に渡されるものではありません（`tools/docker/fetch-engines.py:32-40,165-177`; `tools/docker/publish.sh:70-85`; `tools/docker/build.sh:26-47,130-134`; `tools/docker/Dockerfile:67-83,119-127`）。

## 値と判定

workflow は plan job が release feed にある package だけを matrix に出すため、通常この変数には `cuda13`、`cuda12`、`rocm-gfx120x`、`rocm-gfx110x`、`rocm-gfx1151`、`rocm-igpu`、`sycl` のうち選ばれた値が設定されます。plan job は入力 `flavors` が空なら候補全体を調べ、空でなければその指定を `fetch-engines.py --flavors` に渡します。`fetch-engines.py` はカンマ分割後の各値を `FLAVORS` のキーと照合し、未知の値は argparse error にします（`.github/workflows/docker-images.yml:19-23,55-68,77-81,98-104`; `tools/docker/fetch-engines.py:32-40,122-139`）。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| workflow の `image` step | matrix が空なら job 自体に matrix item がなく、step は起動しません。plan job は package 候補が 0 件なら `the release has no engine package for any requested flavor` を出して失敗します。 | `fetch-engines.py` のキーとして認識され、plan job で package が見つかった値。 | 通常の workflow では無効値は matrix に進みません。直接 `publish.sh` へ未知値を渡すと `fetch-engines.py` が `unknown flavor ... (known: ...)` を出して停止します。 |
| `publish.sh` / `fetch-engines.py` の引数受け渡し | workflow 内では unset のケースは作りません。仮に shell 値が空なら `--flavors ""` が渡り、`publish.sh` の `${flavors:-...}` が既定の全 flavor 一覧に置き換えます。 | 値は comma-separated flavor 名として扱われ、各名が既知キーである必要があります。`fetch-engines.py` は前後の空白を `strip()` してから完全一致で照合します。 | 大文字小文字を変えた名前、空白を含む未知名などはキーと一致せず、argparse error になります。 |

この workflow の plan job からは有効な候補名しか出ないため、空値や未知値の経路は通常の workflow matrix では到達しません。`publish.sh` は `--flavors` の引数を受けるときに文字列をそのまま保存し、空文字は既定一覧に置換します（`tools/docker/publish.sh:32-39,65-70`; `tools/docker/fetch-engines.py:32-40,136-139`）。

## 有効になる条件

- `Docker images` workflow は `workflow_dispatch` による手動起動です。`FLAVOR` を定義する `image` step は plan job が出力した flavor matrix の各要素に対して実行されます（`.github/workflows/docker-images.yml:12-13,46-50,55-68,70-81,97-104`）。
- `fetch-engines.py` は `linux-x86_64` かつ flavor ごとに定義された backend / variant に一致する package を選びます。`--skip-missing` が指定されるため package がなければその flavor は skip され、plan job の対象から外れます（`tools/docker/fetch-engines.py:32-42,49-54,122-139,149-166`; `.github/workflows/docker-images.yml:62-68`）。
- `publish.sh` が選んだ package の出力に含まれる build flavor (`cuda` / `hip` / `sycl`) を `build.sh --flavor` に渡します。`build.sh` は値をこの3つに限定し、それ以外は `build.sh: --flavor must be cuda, hip or sycl` を stderr に出して終了コード 2 で停止します（`tools/docker/fetch-engines.py:32-40,165-177`; `tools/docker/publish.sh:70-82`; `tools/docker/build.sh:26-47`）。
- Dockerfile の追加 package 選択は Docker build 中だけです。`cuda` は基本 package 群のまま、`hip` は AMD 関連ライブラリ、`sycl` は Level Zero / Intel OpenCL 関連ライブラリを追加し、他値は `FLAVOR must be cuda, hip or sycl` を出して build を失敗させます（`tools/docker/Dockerfile:69,74-83`）。
- `push` 入力は workflow 内の別環境値で、image の push を切り替えます。`FLAVOR` は build 対象と flavor tag の選択を担い、push の有無を変えません（`.github/workflows/docker-images.yml:24-28,97-104`; `tools/docker/publish.sh:83-98`）。

## 実行時の詳細

GitHub Actions は matrix item を `image` job の該当 step で `FLAVOR` に設定し、その step の shell が一度 `$FLAVOR` を展開して `publish.sh --flavors` に渡します。workflow による `FLAVOR` の再読み込みや cache はありません（`.github/workflows/docker-images.yml:77-81,97-104`）。

`publish.sh` は `--flavors` を comma-separated 値として処理し、各 flavor について `fetch-engines.py` を実行します。package がある場合は出力2列目の build flavor を `build.sh --flavor` に渡し、`build.sh` は `docker build --build-arg "FLAVOR=$flavor"` を実行します。Dockerfile 内の `ARG FLAVOR=cuda` は runtime image stage の build argument であり、選んだ package 群のシステム依存 package と image metadata label の作成に使われます（`tools/docker/publish.sh:32-39,63-82`; `tools/docker/fetch-engines.py:165-177`; `tools/docker/build.sh:26-47,130-134`; `tools/docker/Dockerfile:67-83,119-127`）。

この値は Strata の engine や Terminal のプロセスへ環境変数として転送されません。Dockerfile の `ARG` は build 時の選択に限られ、ここに示したコードでは container 起動後に `FLAVOR` を読む処理はありません（`.github/workflows/docker-images.yml:97-104`; `tools/docker/build.sh:130-134`; `tools/docker/Dockerfile:67-83,119-127`）。

## ログと測定値

plan job は有効な flavor が0件なら `the release has no engine package for any requested flavor` を出力し、終了コード 1 で止まります（`.github/workflows/docker-images.yml:66-68`）。未知の flavor は `fetch-engines.py` が `unknown flavor <値> (known: <一覧>)` を argparse error として出します（`tools/docker/fetch-engines.py:136-139`）。Docker build 側で `FLAVOR` が `cuda` / `hip` / `sycl` 以外なら `FLAVOR must be cuda, hip or sycl` を出して失敗します（`tools/docker/Dockerfile:77-82`）。値が有効な通常経路では workflow 自身が `FLAVOR` 用のログを出すのではなく、下流の fetch/build のログに flavor が現れます（`tools/docker/publish.sh:66-74,96-100`; `tools/docker/fetch-engines.py:149-166`）。測定値の記載はありません。

## 根拠

- `.github/workflows/docker-images.yml:12-13,55-68,70-81,97-104`: 手動実行、候補の絞り込み、matrix と `FLAVOR` step 環境変数の設定、`publish.sh` への引き渡し。
- `tools/docker/fetch-engines.py:32-42,49-54,122-139,149-177`: flavor 名と package 条件、入力検証、package 不在時の処理、build flavor の出力。
- `tools/docker/publish.sh:32-39,63-85,96-100`: CLI 引数の受け取り、空値時の既定値、package build / skip、各 flavor の処理。
- `tools/docker/build.sh:26-47,130-134`: build flavor の引数検証と Docker build argument への設定。
- `tools/docker/Dockerfile:67-83,119-127`: build argument による依存 package 選択と image label。

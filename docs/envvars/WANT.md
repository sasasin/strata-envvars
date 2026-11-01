# `WANT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`WANT` は、手動起動する GitHub Actions の `Docker images` workflow で、release package を調べて Docker image を作る flavor を選ぶための一時的な環境変数です。workflow の `flavors` 入力が step の環境変数 `WANT` に渡され、入力が空でなければ `docker/fetch-engines.py --flavors` に転送されます。Strata engine / Terminal の実行時設定として読むコードは見つかりませんでした。

workflow の `flavors` 入力は任意で、既定値は空文字です。workflow 自体は `workflow_dispatch` で手動起動する設定です（`.github/workflows/docker-images.yml:12-23,55-64`）。

## 値と判定

| `WANT` の状態 | workflow の処理 |
|---|---|
| 未指定または空文字 | `[ -n "$WANT" ]` が偽になり、`--flavors` を渡さない。`fetch-engines.py` の既定 flavor 一覧全体を調べ、release に package があるものを後続の image job に渡す。 |
| 非空 | `--flavors $WANT` として渡す。値はカンマ区切りで、各 flavor 名は `cuda13`、`cuda12`、`rocm-gfx120x`、`rocm-gfx110x`、`rocm-gfx1151`、`sycl` のいずれかでなければならない。 |
| 未知の名前 | `fetch-engines.py` が未知の flavor と既知名一覧を argparse エラーとして stderr に出し、終了コード 2 で停止する。 |

値そのものを数値や真偽値に変換する処理はありません。Python 側はカンマで分割し、各要素の前後空白を `strip()` で除いてから、既知名と大文字小文字を区別して照合します（`docker/fetch-engines.py:33-40,100-116`）。workflow の shell は `$WANT` を引用符なしで `args` に連結し、その `args` も引用符なしで展開するため、空白を含む値は shell の引数分割を受けます（`.github/workflows/docker-images.yml:61-64`）。

## 有効になる条件

- workflow を GitHub Actions の `Docker images` として手動起動したときだけ使われます。通常の Strata 起動、CLI、サーバーモード、モデル状態には関与しません（`.github/workflows/docker-images.yml:12-23,55-64`）。
- `WANT` が空の場合の全 flavor は `fetch-engines.py` が定義する6種類です。実際に後続へ進むのは release feed に Linux x86-64 package が存在する flavor です。workflow は `--skip-missing` を指定し、package のない flavor を一覧から除外します（`docker/fetch-engines.py:32-41,48-53,125-138`; `.github/workflows/docker-images.yml:62-68`; `docs/DOCKER.md:327-342`）。
- 有効な flavor が一つも残らない場合は `the release has no engine package for any requested flavor` を出して plan job が終了コード 1 になります（`.github/workflows/docker-images.yml:66-68`）。未知の flavor は package の有無を調べる前に argparse が拒否します（`docker/fetch-engines.py:108-123`）。
- 選ばれた flavor は plan job の出力を通じて image job の matrix になります。`push` 入力は別に公開動作を切り替えるため、`WANT` は image 選択だけを担います（`.github/workflows/docker-images.yml:70-81,97-104`）。
- OS / backend 条件は package 選択時に Linux x86-64 と flavor ごとの feed backend・variant で判定されます（`docker/fetch-engines.py:32-41,48-53`）。この `WANT` の読み取り自体には build macro や GPU driver の条件はありません。

## 実行時の詳細

GitHub Actions が `inputs.flavors` を step 起動時に `WANT` に設定し、shell がその時点の値を一度参照します。shell は `--release-tag $TAG --list --skip-missing` に、`WANT` が非空の場合だけ `--flavors $WANT` を追加して `fetch-engines.py` を実行します。結果の `list.tsv` から `SKIP` 行を除いて flavor 一覧を作り、`GITHUB_OUTPUT` に出力します。その出力が image job の matrix に使われます（`.github/workflows/docker-images.yml:55-68,70-81`）。プロセス内 cache や再読み取り、CLI による上書きはありません。

同名の別参照として `tools/hip/build_windows.bat:44-51` は `setlocal` の中で `WANT` を `STRATA_ROCM_VERSION` と `EXTRAS` から設定し、既存 stamp と比較して ROCm wheel の再インストール要否を決めています（同ファイル `:4,41-51`）。これは外から渡された `WANT` を読む処理ではなく、この batch 内で作るローカル変数です。ベンチマーク記録中の `WANT` 参照も調査対象の実装経路ではありません。

## 根拠

- workflow 入力の定義と環境変数の設定・参照: `.github/workflows/docker-images.yml:12-23,55-68`
- 選択した flavor の image job への接続: `.github/workflows/docker-images.yml:70-81`
- flavor の許容名、引数の既定値、値検証、未知値のエラー、feed 内 package の選択: `docker/fetch-engines.py:32-53,100-138`
- workflow の手動起動と空入力時の意図、package のない flavor の除外: `docs/DOCKER.md:312-342`
- 同名だが外部入力ではない batch 内変数: `tools/hip/build_windows.bat:4,41-51`

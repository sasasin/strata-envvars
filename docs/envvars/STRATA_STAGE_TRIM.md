# `STRATA_STAGE_TRIM`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

複数 GPU の layer split で、各 GPU にその GPU の担当層に属する dense weights だけをロードさせます。省いた weights が使っていた VRAM は expert cache に回せます。CLI の `--trim-stage-weights` と同じ要求を行います。CUDA/HIP の実装と SYCL 版に同じ環境変数判定があります。

## 値と判定

環境変数の値は、`getenv()` が返した文字列全体を `std::string` にして `"0"` と比較します。

| `STRATA_STAGE_TRIM` | 環境変数による要求 |
|---|---|
| 未設定 | しない |
| 空文字 | しない |
| 文字列全体が `0` | しない |
| 上記以外の非空文字列 | する |

数値や真偽値としての parse はありません。そのため `00`、`0.0`、`false`、` 0` は要求を有効にし、`0` だけが無効です。大文字小文字は比較に関係しません。

CLI の `--trim-stage-weights` または環境変数のどちらかが要求すれば有効候補になります。CLI 指定は環境変数の `0` では取り消せません。環境変数はモデルと layer split の初期化時に評価されます（関数内の `static` キャッシュではありません）。

## 有効になる条件

- GPU を複数使う layer split が必要です。単一 GPU では環境変数だけを指定しても処理は有効にならず、CLI 指定の場合は `--trim-stage-weights needs a layer split across GPUs (ignored)` が stderr に出ます。
- 明示的な `--layer-split` では、先頭 GPU と後続 GPU の各々が担当層の dense weights のみをロードします。
- `--layer-split auto` では split の決定前に先頭 GPU の arena が作られるため、先頭 GPU は trim されません。要求があると後続 GPU の weights のロードを split 決定後まで遅らせ、後続 GPU は担当層だけをロードします。
- PLE tensors は各 GPU に残ります。先頭 GPU で `--mmap-experts` を使う場合、file-tier の routing-aware prefetch のため全層の router weights も残します。

## 実行時の詳細

各 stage のロード時に、pack の `index.txt` を使って担当層の範囲外にある `blk.*` weights（`ple` を含む名前を除く）を skip 対象にします。native dense projection を使う場合も担当層の範囲を設定し、skip 後の weight pool の大きさで arena を確保してロードします。明示 split では先頭 GPU の arena が split 判明後に trim され、後続 GPU は通常その場で読み込みます。auto split では後続 GPU の読み込みを検索後に行います。

trim が適用されると stderr に `strata generate: layer split: CUDA%d loads the dense weights of layers %lld-%lld only` が出ます。後続 GPU のロードが失敗した場合は重みロードエラーを出して処理を失敗させます。expert cache に入る expert が trim なしの場合と変わる可能性があり、資料は出力がわずかに異なる場合があると説明しています。外部依存や GPU 実行を使った再測定は行っていません。

## 根拠

- `src/program/generate.cpp:553-555,2932-2950`: CLI option、環境変数の判定、明示 split と auto split の条件、先頭 GPU の auto 制約。
- `src/program/generate.cpp:2954-2972,3391-3425,3437-3443,4187-4198`: skip 対象の決定、担当層の範囲設定、weight pool の確保・ロード、auto split 後の後続 GPU のロード。
- `sycl/src/program/generate.cpp:2727-2745,2763-2767,3284-3289`: SYCL 版の同じ判定と split 条件。
- `docs/MULTI_GPU.md:125-131`: 明示 split での目的と、GPU cache 内容の違いにより出力が変わり得るという注意。
- `docs/BATCHING.md:90`: `--trim-stage-weights` と `STRATA_STAGE_TRIM=1` の対応。説明は explicit split を対象にしており、auto split の後続 GPU に関する実装上の例外は上記ソースから確認した。

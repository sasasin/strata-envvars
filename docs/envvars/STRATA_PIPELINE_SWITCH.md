# `STRATA_PIPELINE_SWITCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PIPELINE_SWITCH` は通常の真偽値設定ではなく、pipeline windows の試験用スイッチファイルのパスです。サーバーの各要求でそのファイルを読み、`pw`（prompt/decode window pipeline の段階）、`theta`、`force_miss`、`short_read` の値を上書きします。実際に有効になるには、別途 `STRATA_PIPELINE_DEBUG` と起動時の pipeline 設定が必要です。

この環境変数名を含む実装は CUDA 系 `src/program/generate.cpp` と SYCL 系 `sycl/src/program/generate.cpp` のサーバー生成経路にあります。両方で同じファイル形式を読みます。`docs/DETAILS.md` にこのスイッチファイルの利用者向け説明は見当たらず、実装コメントでは testing 用とされています。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空、または先頭文字が `0` | 共通 helper が対象名の値を取得せず、この変数は無効。`0anything` も無効。 |
| `STRATA_PIPELINE_DEBUG` が上記以外 | 対象変数の値をファイルパスとして取得する。空文字も helper 上は設定値だが、`fopen("")` は失敗するためファイル内容による上書きはない。 |
| 対象変数が未設定 | スイッチファイルを開かず、CLI 由来の既定値を使う。 |
| パスのファイルを開けない | 無言でスイッチファイルの処理を飛ばし、既定値を使う。 |
| ファイルを開ける | 先頭から最大255 byteを読み、そこに含まれる各キーを探す。キーがない項目は既定値を保つ。 |

ファイル中のキーは `strstr` で最初の部分一致を探し、その直後を `atoi` / `atof` / `atoll` に渡します。区切り文字や行形式の検証、数値文字列全体の検証はありません。変換できない文字列は各 C 変換関数の規則により通常 0 になります。

| キー | 変換・制限 | 適用される値 |
|---|---|---|
| `pw=` | `atoi` の結果を `[0, 2]` に clamp | 0 は pipeline windows を要求しない。1 以上は対応条件下で prompt の window pipeline を使う。2 は追加条件を満たせば decode の window pipeline も要求する。 |
| `theta=` | `atof` を `float` に変換。範囲制限なし | speculative window の判定閾値を上書きする。 |
| `force_miss=` | `atoi` の結果を 0 以上に clamp | 0 は forced miss なし。正値はテスト用の強制 miss 間隔を上書きする。 |
| `short_read=` | `atoll` の結果を 0 以上に clamp | prompt の verify windows に送る区間長の上限を要求ごとに上書きする。 |

数値の前後の空白や数値の後ろの文字列は専用に検査されません。たとえば `pw=2junk` は `atoi` により 2 として扱われ、`pw=-1` は 0、`pw=9` は 2 になります。`theta=` には clamp がなく、値の妥当性や有限性もこの処理では確認されません。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` は `pipe_dbg_env()` 内の `static const bool` で初回評価時に一度判定されます。未設定・空・先頭が `0` の場合は対象変数を含む `STRATA_PIPELINE_*` helper 読み取りが無効になります。それ以外（例: `1`, `true`, 空白始まり）は有効です。
- スイッチファイルのパスも要求処理内の `static const char*` として一度取得されます。したがってプロセス実行中に `STRATA_PIPELINE_SWITCH` 自体を書き換えても再取得されません。一方、同じパスのファイル内容は `fopen` / `fread` により各要求で読み直されます。
- 読み取り場所は `pipe_dbg_env("STRATA_PIPELINE_SWITCH")` の後に `&& pipe` で条件付けられています。`pipe` は起動時に pipeline windows が有効で、複数 GPU の layer split などの条件を満たすときだけ真になります。CUDA では複数 stage の layer split 経路、SYCL では二 stage の layer split 経路です。通常の単一 GPU 実行や pipeline windows が起動時に無効な経路では、このファイル値は使われません。
- 起動時の有効化は別設定です。明示した `--pipeline-windows` は 0〜2 に clamp されます。自動設定 (`o.pipeline_windows < 0`) では `STRATA_PIPELINE_AUTO=0` が自動有効化を止めます。CUDA/HIP 共用コードでは自動有効化が HIP macro と GPU/モデル等の条件に限られ、SYCL では Intel GPU 世代などの判定を使います。いずれの場合も、`STRATA_PIPELINE_SWITCH` の要求時 `pw=` は起動時に確保される機能・リソースを変更しません。
- `pw` は要求ごとに起動時の `o.pipeline_windows` を初期値として設定され、ファイルの `pw=` があれば上書きされます。そのためこの環境変数だけで、起動時に pipeline 機能が無効だった状態を有効化することはできません。`pw=0` による要求単位の無効化は可能です。
- `pw>=1` の prompt pipeline は、CUDA では `pipe && n_stages == 2`、SYCL では `pipe` のときに選択され、`STRATA_LOGPOS` が設定されている要求ではシリアル経路になります。
- `pw>=2` の decode pipeline は snapshot 準備が済んでいることも必要です。さらに履歴に対する repetition penalty や coupled draft sampling がある要求では decode はシリアル経路に戻ります。必要な snapshot などが起動時に用意されていない場合も実行されません。
- `short_read=` はその要求の CLI `--short-read` 由来の値を上書きします。区間長が値を超える場合、または `STRATA_CKPT_REREAD` が設定されている場合や画像 embedding row を含む場合には、該当区間は verify windows を使いません。0 にすると通常の正の長さの区間は window 対象外です。

## 実行時の詳細

要求処理では `pl_pw` を pipeline startup 設定、または `pipe` が偽なら 0 で初期化します。ファイルが開けた場合に限り、認識した各キーでその要求のローカル値を更新します。`short_read` は `req_short_read` に入り、`windows_ok` が prompt 区間の長さと照合します。`pw>=1` は対応する二 stage / SYCL pipeline 経路で prompt windows の処理を切り替え、`pw>=2` は decode pipeline を試みる条件に使われます。これらは要求単位の制御で、CLI の `--pipeline-windows` や起動時に確保される pipeline 用リソースを置き換えません。

ファイルが読めた要求では stderr に次の形式で処理後の値を出します（文言は実装どおりです）。ファイルを開けない場合、この行も出ません。

```text
strata pipeline switch: pw=%d theta=%.3f force_miss=%d short_read=%lld
```

スイッチファイル自体の読込失敗による終了や警告はありません。pipeline 実行に入った後の準備・検証失敗には別のエラー経路がありますが、この環境変数の読み取り処理自体は失敗を返しません。

## 根拠

- `src/program/generate.cpp:461-467` — `STRATA_PIPELINE_DEBUG` の値判定と、その結果に応じた helper 経由の取得。
- `sycl/src/program/generate.cpp:298-303` — SYCL 側の同じ helper。
- `src/program/generate.cpp:14777-14801`, `sycl/src/program/generate.cpp:10428-10452` — 要求ごとのパス利用、最大255 byteの読込、キー検索・変換・clamp、stderr ログ。
- `src/program/generate.cpp:3256-3258` — CLI `--short-read` と `--pipeline-windows` の値制限。
- `src/program/generate.cpp:4985-5020`, `sycl/src/program/generate.cpp:3421-3462` — 自動 pipeline 判定と `STRATA_PIPELINE_AUTO`、CLI 指定、serve・layer split・モデル・backend 等の起動条件。
- `src/program/generate.cpp:10000-10005`, `sycl/src/program/generate.cpp:7325-7329` — pipeline 実行経路が成立する条件。
- `src/program/generate.cpp:14892-14897`, `sycl/src/program/generate.cpp:10554-10558` — prompt pipeline の適用条件。`src/program/generate.cpp:14894-14896` は三 stage 以上では prompt window をシリアルで処理することも示す。
- `src/program/generate.cpp:16087-16098`, `sycl/src/program/generate.cpp:11037-11048` — decode pipeline の `pw>=2`・snapshot 条件、要求状態によるシリアル fallback。
- `src/program/generate.cpp:14770-14776`, `sycl/src/program/generate.cpp:10420-10426`; `src/program/generate.cpp:14896`, `sycl/src/program/generate.cpp:10891-10903` — `short_read` を区間ごとに適用する判定と、その後の prompt 処理。

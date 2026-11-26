# `STRATA_KV_ROT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--kv int8` の K/V キャッシュに Hadamard 回転を適用する opt-in です。生成開始時に値を読み、INT8 K/V 回転フラグを設定します。フラグが有効な状態では、K/V をキャッシュに格納する前に回転し、attention に使う query 側も回転、attention 出力を逆回転（Hadamard 変換は自己逆）します。回転を使うかは生成時に選ばれた K/V 形式にも依存します。CUDA/HIP 実装と SYCL 実装に読み取りがあります（`engine/src/program/generate.cpp:5014-5027`、`engine/sycl/src/program/generate.cpp:2528-2541`）。

この変数は K/V 形式そのものを選びません。`--kv int8` と組み合わせて初めて INT8 キャッシュの回転を有効にします。`--kv q4_0` は変数に関係なく回転し、`--kv fp16` と `--kv k8v4` ではこの INT8 回転フラグは K/V の回転条件になりません（`engine/src/core/layer.cpp:807-823`）。

## 値と判定

両方の生成実装で `getenv` の結果が非 null で、先頭文字が ASCII `1` かどうかだけを判定します。文字列全体の比較や数値変換はしません。したがって未設定・空文字は無効、`1`・`10`・`1anything` は有効、`0`・`true`・`01`・` 1` は無効です。大文字小文字、後続文字、数値としての妥当性は検査しません（`engine/src/program/generate.cpp:5023-5026`、`engine/sycl/src/program/generate.cpp:2537-2540`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP または SYCL の生成実装 | INT8 回転フラグは false | 先頭文字が `1`（例: `1`, `10`, `1x`） | 先頭文字が `1` 以外（例: 空文字、`0`, `true`, `01`, ` 1`） |

`--kv` は別に検証され、`q4` は `q4_0` に正規化されます。許容値は `fp16`, `int8`, `q4_0`, `k8v4` です。変数に `1` があっても `--kv` が `int8` でなければ INT8 回転にはなりません（`engine/src/program/generate.cpp:5014-5027`）。

## 有効になる条件

- `STRATA_KV_ROT` の先頭文字が `1` であること。
- INT8 キャッシュの回転には、CLI で `--kv int8` が選択されていること。これにより `st.kv_int8` が true となり、設定された回転フラグと合わせて `st.kv_rot` が true になります（`engine/src/core/layer.cpp:807-823`）。
- 生成実装が CUDA/HIP (`engine/src/program/generate.cpp`) または SYCL (`engine/sycl/src/program/generate.cpp`) であること。これらに変数の読み取りがあります。現行ソースで Metal 実装からの読み取りは見つかりませんでした。
- `--kv q4_0` では `st.kv_rot` が K/V 形式自体から true になります。環境変数の設定は Q4_0 の回転を切り替えません。`--kv fp16` では INT8 条件が成立せず、`--kv k8v4` は hybrid の別経路で K は未回転、V は Q4_0 形式側の回転です（`engine/src/core/layer.cpp:813-823, 1235-1262`）。

`--kv` と環境変数の優先順位を比較する上書き処理はありません。`--kv` がキャッシュ形式を選び、この変数は INT8 時の回転フラグを追加します。

## 実行時の詳細

通常の `strata generate` と serve 用生成エンジンの初期化経路で、`--kv` の検証後に環境変数を読み、`qsa_set_kv_int8_rotate` に結果を渡します。設定値は `engine/src/core/layer.cpp:204-210` のプロセス内フラグに保持され、QSA state 初期化時に K/V 形式と組み合わせて `st.kv_rot` に確定します（`engine/src/core/layer.cpp:807-823`）。SYCL 側も同じ setter を使います（`engine/sycl/src/program/generate.cpp:2533-2541`）。この読み取りは生成初期化時で、リクエストごとの再読込やこの変数用の static cache はありません。通常の外部環境変更は既に起動したプロセスの環境を変えないため、起動済みエンジンの回転設定は変わりません。

`st.kv_rot` が true の場合、decode では K/V をキャッシュへ追加する前に回転し、query を回転して attention を行い、attention 出力を戻します（`engine/src/core/layer.cpp:1244-1262, 1284-1316`）。prefill と speculative verification にも同じ state flag による K/V・query・出力の回転分岐があります（`engine/src/prefill/prefill.cpp:5291-5316, 5565-5574`、`engine/src/core/verify.cpp:2340-2347, 2578-2594`）。SYCL の decode 実装にも同じ state flag の分岐があります（`engine/sycl/src/core/layer.cpp:1256-1262, 1306-1343`）。

サーバーのセッション保存・復元では、設定 fingerprint を初めて必要とした時点でこの環境変数をもう一度読み、先頭文字が `1` かを `kv_rot` として記録します。その fingerprint はプロセス内でキャッシュされます（`engine/src/program/generate.cpp:13960-14029`、SYCL: `engine/sycl/src/program/generate.cpp:8178-8208`）。この fingerprint は `--kv` などとともに保存状態の互換性判定に使われます（`engine/src/core/conversation_file.cpp:878-899, 1267`）。そのため、`--kv` が INT8 でなくても、保存時と復元時でこの値の判定が異なれば設定 fingerprint が合わず復元は拒否されます。Strata の `docs/DETAILS.md:935-939` もセッションファイルが `STRATA_KV_ROT` を含む設定に束縛されると記載しています。

## ログと測定値

先頭文字が `1` で、かつ `--kv int8` の場合に限り、stderr に次の行を出します。

```text
strata generate: STRATA_KV_ROT=1: INT8 K/V through the Hadamard rotation (opt-in)
```

このログは設定値と `--kv` の組み合わせを示します。`--kv q4_0` だけで回転する場合にはこの環境変数由来のログは出ません（`engine/src/program/generate.cpp:5023-5026`、`engine/sycl/src/program/generate.cpp:2537-2540`）。

ソースコメントには特定の2パックでの first-token KL 値が記されていますが、測定環境・実行条件が記載されていないため、ここでは一般的な品質・性能の測定値として扱いません（`engine/src/program/generate.cpp:5021-5022`）。値の無効化による専用の警告・終了経路は、該当箇所では見つかりませんでした。

## 根拠

- `engine/src/program/generate.cpp:5014-5027` — `--kv` の値、環境変数の読み取り・判定、INT8 回転設定、ログ。
- `engine/sycl/src/program/generate.cpp:2528-2541` — SYCL 生成実装の同じ判定とログ。
- `engine/src/core/layer.cpp:204-210, 807-823` — 回転フラグの保持と K/V 形式との合成。
- `engine/src/core/layer.cpp:1244-1262, 1284-1316`、`engine/src/prefill/prefill.cpp:5291-5316, 5565-5574`、`engine/src/core/verify.cpp:2340-2347, 2578-2594` — decode / prefill / verify における回転処理。
- `engine/src/program/generate.cpp:13960-14029`、`engine/src/core/conversation_file.cpp:878-899, 1267` — 保存・復元設定 fingerprint への反映。
- `docs/DETAILS.md:935-939` — 設定 fingerprint に関する説明との照合。

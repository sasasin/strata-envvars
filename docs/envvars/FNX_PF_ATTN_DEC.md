# `FNX_PF_ATTN_DEC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の prompt prefill で、attention 層の処理に decode 経路の `attn()` を使うか選びます。有効時は QSA の行グループ幅を `attn_rows()` にし、各グループで `attn()` を実行します。無効時は QSA の選択後、prompt 専用の attention 部分計算・カード間交換・merge を使います。名前に `DEC` とありますが、この値を読む場所と分岐は `Engine::prefill()` の prompt 処理にあります。

対象は `src/split` の all-cards split engine です。ビルド時に `STRATA_BUILD_SPLIT=ON` が必要で、CMake は Linux CUDA または HIP の構成だけを対象にします。通常の Strata engine や他の backend に同名の読み取りはありません（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-30`）。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` です。`env_int()` は環境変数が未設定なら既定値を返し、設定されていれば符号付き base-10 整数として文字列全体を `long long` に解析します（`src/split/src/env.hpp:15-21,33-40,51-52`）。

| 環境値 | 判定 |
|---|---|
| 未設定 | `0` として無効 |
| `0`, `+0`, `-0` | 無効 |
| 有効な整数で 0 以外（例: `1`, `-1`, `2`, `+1`） | 有効 |
| 空文字、前後の空白、整数以外、末尾に余分な文字、`long long` 範囲外 | 不正値として例外 |

値に範囲 clamp はありません。整数として解析できる範囲の任意の非ゼロ値が有効です。環境変数を読む際に、同名の CLI 引数や設定ファイルによる上書きはありません。

## 有効になる条件

- `strata-split` がビルドされ、その `Engine` の prompt buffers が初期化されること。CMake では split engine は既定 OFF です（`CMakeLists.txt:2945-2949`）。
- prompt path の `Engine::prefill()` が attention 層を処理すること。Strata の server が split engine を起動しない場合、この変数はその通常 engine の挙動を変えません（`src/split/src/prefill.cu:982-984,1199-1238`）。
- 値が未設定または `0` のときは decode attention 分岐を使いません。別の環境変数 `FNX_PF_QSA_ROWS` は無効時に使う QSA 行グループ幅を変更しますが、`FNX_PF_ATTN_DEC` 自体の有効/無効は上書きしません（`src/split/src/prefill.cu:667-674,1220-1237`）。

## 実行時の詳細

`Engine` の構築中、`prefill_alloc()` がカードごとの `Pf` を作り、その中で `FNX_PF_ATTN_DEC` を読み `p->attn_dec` に保存します。`prefill_alloc()` は engine constructor から呼ばれます（`src/split/src/prefill.cu:625-635,768`; `src/split/src/engine.cu:275`）。このため、設定値は各カードの prompt buffers 初期化時に読まれ、リクエストごとには再読されません。engine 起動後にプロセス環境を変更しても、すでに保存された `p->attn_dec` には反映されません。static cache ではありません。

prompt の attention 層では、次の違いがあります（`src/split/src/prefill.cu:1217-1238`）。

- 有効時: グループ幅を `attn_rows()` とし、各グループの QSA 選択後に `attn()` を呼びます。`attn()` はその行数について attention 部分計算、ローカル集約、カード間 merge を実行します。prompt 専用の `pf_attn_start()` / `pf_attn_finish()` は通りません（`src/split/src/kernels.cu:1385,1388-1402`）。
- 無効時: グループ幅は既定 `qsa_pf_rows`（256）または `FNX_PF_QSA_ROWS` の値です。attention 部分計算と交換は `pf_attention()` を通り、overlap が有効なら `pf_attn_start()` と後続の `finish_att()` に分けて実行されます（`src/split/src/prefill.cu:373,553-600,1165-1171,1220-1238`）。
- 有効時の後続 chunk-sum は、`p.overlap` が有効なら `ring_async()`、そうでなければ `pf_ring()` に進みます（`src/split/src/prefill.cu:1241-1246`）。

不正値は `env_int()` が `runtime_error` を送出します（例: `FNX_PF_ATTN_DEC: '' is not a whole number`）。sFNX 起動時には `Engine` の構築が失敗し、`sfnx` は `ERR <理由>` をプロトコル出力、`sfnx: failed: <理由>` を stderr に出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1052-1062,1027-1035`）。有効値・無効値について、この変数専用のログ出力は見つかりません。`fnx_run` の lab modes は engine を作る前に戻るため、これらのモードでは変数を読みません（`src/split/tools/fnx_run.cpp:978-982`）。

## 根拠

- 候補名のソース全体参照: `src/split/src/prefill.cu:349-350,768`。前者はコメントと状態フィールド、後者が唯一の値読み取り箇所です。
- 整数・flag の解析規則: `src/split/src/env.hpp:15-21,33-40,51-52`。
- engine 構築と prompt prefill の分岐: `src/split/src/engine.cu:275`; `src/split/src/prefill.cu:625-635,768,1217-1246`; `src/split/src/kernels.cu:1385,1388-1402`。
- ビルド対象: `CMakeLists.txt:2945-2949`; `src/split/CMakeLists.txt:20-30`。
- 調査対象リポジトリでの候補掲載: `docs/envvars/000_envvers.md:557`。

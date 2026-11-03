# `FNX_PF_SEQ_START`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の prompt path が複数カード間で使う ring と attention exchange の sequence counter の初期値を指定します。これはテスト用フックで、通常の `strata` エンジン向け設定ではありません。対象コードは opt-in の split engine（`-DSTRATA_BUILD_SPLIT=ON`）に含まれ、Linux CUDA または HIP ビルドの `strata-split-<カード数>` サーバー実行ファイルに組み込まれます。CUDA では同じ engine を使う `split_fnx_run` テストドライバーもあります（`src/split/CMakeLists.txt:1-7,20-30,64-79,92-105,153-160`）。

## 値と判定

`env_int()` が環境変数全体を符号付き base-10 整数として読みます。unset の既定値は `0` です。設定値は省略可能な `+` または `-` と10進数字だけを受け付け、先頭・末尾の空白、空文字、数字の後ろの文字、他の形式は受け付けません。`strtoll` が `long long` の範囲を超える値も整数 parse error になります。parse 後は `0..4294967295`（`UINT32_MAX`）に制限されます。

| 入力 | 結果 |
|---|---|
| unset | `0` を使う |
| 空文字または整数でない文字列（例: `1x`, ` 1`） | `FNX_PF_SEQ_START: '<値>' is not a whole number` で初期化失敗 |
| 整数として parse できるが `0` 未満または `4294967295` 超 | `FNX_PF_SEQ_START: want 0..4294967295, got <値>` で初期化失敗 |
| `0..4294967295` | unsigned counter の初期値にする |

`+1`、`-0` も整数として受理され、それぞれ `1`、`0` になります。CLI 引数や別の設定値による上書きはこのコードにはありません（`src/split/src/env.hpp:15-21,33-40`; `src/split/src/prefill.cu:908-911`）。

## 有効になる条件

対象は `src/split` の split engine のみです。CMake は split engine を opt-in とし、Linux CUDA または HIP 以外では構成をスキップします。CUDA/HIP のどちらにも同じ `prefill.cu` の読み取りが使われ、変数固有の backend 分岐はありません（`src/split/CMakeLists.txt:1-7,20-30,64-79,92-105`）。

値が範囲内でも、初回 prompt read の開始時に counter が `2^31` 以上なら、指定値はそこで使われず `0` に reset されます。したがって初回 read に持ち越されるのは `0..2^31-1` の範囲です。後続の通常 reset も `0` に戻します（`src/split/src/engine.hpp:235-240`; `src/split/src/prefill.cu:982-988`）。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、その prompt path 初期化の最後でこの変数を読みます。読み取った値は全カードについて ring flags と attention flags をゼロ化した後、各カードの `p.seq`、`p.att_seq[0]`、`p.att_seq[1]` に設定されます。ring sum と attention exchange は `++p.seq` で次の sequence 番号を作るため、counter に設定した値自体ではなく、その次の番号から使います。sequence 番号は flag の待ち合わせにも使われます（`src/split/src/engine.cu:274-275`; `src/split/src/prefill.cu:611-623,908-911,512-534,541-560`; `src/split/src/engine.hpp:235-240`）。

読み取りは `Engine` 構築ごとに一度で、リクエストごとではありません。構築後にプロセス環境を変えても、その `Engine` の counter には反映されません。`prefill()` の開始時に counter が `1u << 31` 以上なら、stderr に `fnx: prompt ring sequence numbers at %u: flags zeroed, numbers from 0 again` を出し、flags と counter を `0` に戻します（`src/split/src/prefill.cu:908-911,982-988`）。

範囲外または不正な値は prompt 処理開始前の `Engine` 初期化を失敗させます。`sfnx` は stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します。`fnx_run` は stderr に `fnx_run: <理由>` を出して終了コード 1 になります（`src/split/tools/sfnx.cpp:1051-1062,1027-1035`; `src/split/tools/fnx_run.cpp:1365-1373`）。

## 根拠

- 読み取り、既定値、明示範囲、初期 reset: `src/split/src/prefill.cu:908-911`。
- 整数 parse（符号、全体一致、空文字・不正文字・overflow の拒否）: `src/split/src/env.hpp:15-21,33-40`。
- counter と flags の reset: `src/split/src/prefill.cu:611-623`。
- sequence counter の increment と ring / attention exchange への利用: `src/split/src/prefill.cu:512-534,541-560`。
- prompt ごとの threshold reset とログ: `src/split/src/prefill.cu:982-988`。
- 初期化時の呼び出し元: `src/split/src/engine.cu:274-275`。
- flag sequence の用途と reset threshold の注記: `src/split/src/engine.hpp:235-240`。
- split engine の build 条件: `src/split/CMakeLists.txt:1-7,20-30,64-79,92-105`。
- 起動失敗の観測経路: `src/split/tools/sfnx.cpp:1027-1035,1051-1062`; `src/split/tools/fnx_run.cpp:1365-1373`。

# `FNX_GDN_TIME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この変数は split engine のプロンプト処理における GDN 計算時間を計測する診断用スイッチです。`gdn_prompt` が呼ばれると、無効時は通常の `gdn_prompt_impl` を実行し、有効時は CUDA event を GDN 処理の前後に記録して GPU 時間を集計します。GDN の計算内容や経路選択を変える設定ではなく、CLI 引数による上書きもありません（`engine/src/split/src/kernels.cu:2073-2092`）。

呼び出し元は split prefill の非 attention 層の処理です。したがって、split engine でプロンプト中にこの処理へ到達した場合だけ評価されます（`engine/src/split/src/prefill.cu:1651-1657`）。通常の測定値を示す資料上の数値はこの変数の実装箇所にはありません。

## 値と判定

`fnx::env_int("FNX_GDN_TIME", 0)` が環境から値を取得します。未設定なら既定値 `0` で計測しません。設定値は10進の符号付き `long long` として文字列全体を parse し、0以外なら計測を有効にします。空文字、`true` / `false`、前後の空白、`0anything` などは整数として受理されず例外になります。数値範囲の独自 clamp はなく、`long long` の範囲外も無効です（`engine/src/split/src/env.hpp:15-22,33-40`）。

| 条件（build など） | unset | 設定時に有効になる値（例） | 無効値・無効になる値（例） |
|---|---|---|---|
| split engine の GDN プロンプト経路 | `0`（無効） | `1`、`-1`、`+2`（整数全体が0以外） | `0`、`00`（整数値0）；空文字、`true`、`0anything`、` 1`、範囲外整数（parse エラー） |

値の parse は `gdn_prompt` 内の関数ローカル `static const bool` の初期化時に行われます。最初の呼び出しで決まり、その後のプロセス内で環境値を変更しても再評価されません（`engine/src/split/src/kernels.cu:2073-2077`）。

## 有効になる条件

- split engine を含む CUDA または HIP build であること。CMake は split engine の kernel parts と prefill 実装を両 backend 向けに構成します。対象箇所は `FNX_KPART == 4` の条件付きコードにあります（`engine/src/split/CMakeLists.txt:77-101`; `engine/src/split/src/kernels.cu:1913-1917,2073-2076`）。
- split prefill が非 attention 層で `gdn_prompt` を呼ぶこと。変数は decode の `gdn_core` / `gdn_core_lanes` / `gdn_core_segs` では参照されません（`engine/src/split/src/prefill.cu:1651-1657`; `engine/src/split/src/kernels.cu:1923-1999,2073-2079`）。
- 値が整数として有効であること。未設定および数値0では通常処理に進み、計測イベントを作りません（`engine/src/split/src/kernels.cu:2076-2080`）。

モデル状態、CLI オプション、他の環境変数による優先順位や上書きはありません。対象処理に到達しない実行では、非0の設定でもこの変数の読み取り・計測は起きません（`engine/src/split/src/prefill.cu:1651-1657`; `engine/src/split/src/kernels.cu:2073-2080`）。

## 実行時の詳細

有効時、各 `gdn_prompt` 呼び出しで現在の device と stream を取得し、前後の CUDA event を記録して `gdn_prompt_impl` を実行します。終了 event は `pend` に追加され、後続呼び出しで `cudaEventQuery` が完了を返した記録だけを集計します。そのため集計は呼び出しより遅れて進み、明示的な GPU 同期待ちはありません（`engine/src/split/src/kernels.cu:2081-2100`）。

集計は thread-local な device ごとの状態に保持されます。完了した記録の行数が累積 `36 * 32768` 以上になると、その device の累積 GPU 時間・呼び出し数・行数・1行あたり時間を stderr に出し、カウンターをリセットします。しきい値を超えたタイミングで未完了記録があれば、それが完了するまで出力は後になります（`engine/src/split/src/kernels.cu:2082-2105`）。

無効値を最初の GDN プロンプト呼び出しで読むと、helper が `std::runtime_error` を送出します。sfnx の実行中例外処理は `ERR <例外文>` をプロトコル出力へ送り、stderr に `sfnx: failed: <例外文>` を出して終了コード1で終了します（`engine/src/split/src/env.hpp:33-39`; `engine/src/split/tools/sfnx.cpp:1097-1102,1160-1166`）。

## ログと測定値

計測ログは stderr に次の形式で出ます。文字列は `engine/src/split/src/kernels.cu:2101-2104` によります。

```text
gdn time: card <device>: <累積ms> ms GPU over <呼び出し数> calls, <累積行数> rows (<ms/row> ms a row)
```

この値は完了済み CUDA event 区間の Strata 内集計です。実測結果や性能向上率ではありません。無効時はこのログを出さず、無効値による例外時は上記のエラー経路になります（`engine/src/split/src/kernels.cu:2076-2080,2094-2105`）。

## 根拠

- 候補名の直接参照は `engine/src/split/src/kernels.cu:2076` の1箇所。コメント中の出現も同ファイル `:2071-2072` のみ。
- 整数 parse と未設定時 default: `engine/src/split/src/env.hpp:15-22,33-40`。
- GDN プロンプトの呼び出し条件: `engine/src/split/src/prefill.cu:1651-1657`。
- static cache、通常経路、計測イベントと出力: `engine/src/split/src/kernels.cu:2071-2105`。
- split CUDA/HIP build と kernel part 構成: `engine/src/split/CMakeLists.txt:77-101`; `engine/src/split/src/kernels.cu:1913-1917`。
- sfnx の例外出力と終了処理: `engine/src/split/tools/sfnx.cpp:1097-1102,1160-1166`。

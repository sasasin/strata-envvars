# `STRATA_LOGPOS_TOPK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`Verifier::window_logprobs` が出力する各ログ確率行の末尾に、上位 K 個の token ID と、その行の全語彙 logits に対する log-probability を `id:logprob` 形式で追加します。CUDA/HIP 共通実装と SYCL 実装に読み取りがあります。生成・サンプリングで選ぶ token はこの値で変更されず、追加対象はログファイルの列です。[`engine/src/core/verify.cpp:4501-4518`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4501) [`engine/sycl/src/core/verify.cpp:3135-3152`](../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp#L3135)

この変数だけではログ出力を開始しません。prompt の verify-window 行は `STRATA_LOGPOS` のファイルが開けた場合に、decode の forced continuation 行は `STRATA_FOLLOW` と `STRATA_FOLLOW_LOGPOS` が有効な場合に `window_logprobs` が呼ばれ、そのとき本変数の列が使われます。[`engine/src/program/generate.cpp:20453-20467`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L20453) [`engine/src/program/generate.cpp:21681-21707`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L21681) [`engine/src/program/generate.cpp:23031-23040`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L23031)

## 値と判定

両 backend とも `std::getenv` の戻り値が null なら 0、設定されていれば `std::atoi` で変換し、結果を 0～256 に clamp します。文字列全体の数値検証はありません。`atoi` が読む先頭の整数部分が使われ、後続文字は無視されます（例: `12xyz` は 12、`xyz` と空文字は 0）。先頭空白や符号は `atoi` の変換規則に従います。変換値が負なら 0、256 より大きければ 256 です。数値として `int` に表せない入力に対する `atoi` の結果は規定できません。[`engine/src/core/verify.cpp:4506-4509`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4506) [`engine/sycl/src/core/verify.cpp:3140-3143`](../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp#L3140)

| 条件（build/backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP (`engine/src/core/verify.cpp`)、SYCL (`engine/sycl/src/core/verify.cpp`) | 0（追加列なし） | `1`～`256`、`12xyz`（12 列）、`999`（256 列に clamp） | 空文字、`0`、`0anything`、`-1`、`junk`（いずれも追加列なし） |

`K > 0` なら logits の降順で上位 K token を `std::partial_sort` し、各値を `row[token] - lse` として小数点以下 6 桁で書きます。K は最大 256 に制限されますが、語彙数に合わせた追加 clamp はありません。実装は `order.begin() + K` を使うため、語彙数が K 未満のモデルに対する保護はこの箇所にありません。[`engine/src/core/verify.cpp:4482-4503,4510-4518`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4482) [`engine/sycl/src/core/verify.cpp:3116-3137,3144-3152`](../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp#L3116)

## 有効になる条件

- `window_logprobs` が呼び出される必要があります。prompt の採点経路では `STRATA_LOGPOS` が設定され、追記用ファイルを `fopen(..., "ab")` で開けた場合に呼ばれます。空文字も設定済みとして `fopen` に渡されますが、開けず null なら記録処理は行われません。[`engine/src/program/generate.cpp:20457-20466`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L20457) [`engine/sycl/src/program/generate.cpp:11307-11315`](../../../Niko1221/Strata/engine/sycl/src/program/generate.cpp#L11307)
- decode の forced continuation では `STRATA_FOLLOW_LOGPOS` の出力ファイルが開け、さらに `STRATA_FOLLOW` から forced continuation が読み込まれている必要があります。CUDA/HIP は有効な行がある窓について出力し、SYCL は forced token の vector が空でない場合に出力します。[`engine/src/program/generate.cpp:21684-21707,23031-23040`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L21684) [`engine/sycl/src/program/generate.cpp:11750-11766,12780-12792`](../../../Niko1221/Strata/engine/sycl/src/program/generate.cpp#L11750)
- 実装箇所の設定登録は backends を `cuda-hip` と `sycl` としています。登録情報と `docs/SETTINGS.md` は利用対象を NVIDIA/AMD、Intel Arc と記載しています。[`terminal/data/settings-register.json:21399-21416`](../../../Niko1221/Strata/terminal/data/settings-register.json#L21399) [`docs/SETTINGS.md:158`](../../../Niko1221/Strata/docs/SETTINGS.md#L158)
- `STRATA_LOGPOS_TOPK` は `window_logprobs` 内の関数ローカル `static` で初回に一度だけ読みます。prompt 経路では最初の呼び出し時、forced decode 経路では最初の対象呼び出し時に値が固定され、そのプロセス内の後続呼び出しには環境変更が反映されません。[`engine/src/core/verify.cpp:4506-4509`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4506) [`engine/sycl/src/core/verify.cpp:3140-3143`](../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp#L3140)
- CLI 引数による上書きはありません。`STRATA_LOGPOS_TOPK` はファイル出力先を選ばず、出力先や採点経路は別変数 `STRATA_LOGPOS` / `STRATA_FOLLOW_LOGPOS` が決めます。

## 実行時の詳細

prompt の `read_windows` は、各 verify window の実行後、window 内 token を commit する前に `STRATA_LOGPOS` の出力先が開いていれば `window_logprobs` を呼びます。出力は各窓の行ごとで、既存の列（位置、正解 token、正解 token の log-probability、argmax 等）の後ろに K 個の `id:logprob` 列がタブ区切りで続き、ファイルへ追記して flush されます。`STRATA_LOGPOS` が設定されていると、二段 pipeline の prompt read を並列経路にせず serial の窓経路にします。[`engine/src/program/generate.cpp:20414-20425,20445-20467,20479-20485`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L20414) [`engine/src/core/verify.cpp:4501-4521`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4501)

forced decode の `STRATA_FOLLOW_LOGPOS` 経路も同じ verifier 関数を使うため、K 列が適用されます。SYCL 側の呼び出しには prompt 採点の `STRATA_LOGPOS` 条件がなく、forced decode のログ出力は独立しています。[`engine/src/program/generate.cpp:23031-23040`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L23031) [`engine/sycl/src/program/generate.cpp:12780-12792`](../../../Niko1221/Strata/engine/sycl/src/program/generate.cpp#L12780)

## ログと測定値

本変数自体に関する有効・無効ログや値エラーのログはありません。上位 K 列はログファイルへの出力です。prompt 採点で logits が使えない場合や head logits のコピーに失敗した場合、verifier は `window_logprobs: no head logits for this window` または `window_logprobs: the head logits copy failed` を返します。prompt の呼び出し元はその失敗を伝播し、read を失敗させます。CUDA/HIP の forced decode 呼び出し元は stderr に `strata serve: STRATA_FOLLOW_LOGPOS: <理由>` を出し、SYCL は `ERR <理由>` を stdout に出して終了コード 1 で戻ります。[`engine/src/core/verify.cpp:4435-4465`](../../../Niko1221/Strata/engine/src/core/verify.cpp#L4435) [`engine/sycl/src/core/verify.cpp:3105-3111,3156-3159`](../../../Niko1221/Strata/engine/sycl/src/core/verify.cpp#L3105) [`engine/src/program/generate.cpp:23038-23040`](../../../Niko1221/Strata/engine/src/program/generate.cpp#L23038) [`engine/sycl/src/program/generate.cpp:12790-12792`](../../../Niko1221/Strata/engine/sycl/src/program/generate.cpp#L12790)

## 根拠

- CUDA/HIP の値読み取り、順位付け、列出力: `engine/src/core/verify.cpp:4482-4518`
- SYCL の値読み取り、順位付け、列出力: `engine/sycl/src/core/verify.cpp:3116-3152`
- prompt 採点の出力開始と呼び出し: `engine/src/program/generate.cpp:20414-20467`; `engine/sycl/src/program/generate.cpp:11277-11317`
- forced decode の出力条件とエラー経路: `engine/src/program/generate.cpp:21681-21707,23031-23040`; `engine/sycl/src/program/generate.cpp:11750-11766,12780-12792`
- backend 登録と設定一覧: `terminal/data/settings-register.json:21399-21416`; `docs/SETTINGS.md:158`
- 使用例: `docs/QUANTS.md:60`; `docs/UNSLOTH_Q4.md:199,224`

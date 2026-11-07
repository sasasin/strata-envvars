# `STRATA_FORCE_FAULT`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

テスト用の fault injection です。`Verifier::window_logprobs()` が head logits を host メモリへコピーした後、スコア計算前に、指定した剰余を持つ token ID の logit へ bias を加算します。これは `STRATA_LOGPOS` または `STRATA_FOLLOW_LOGPOS` の診断・採点行を意図的に変えるフックで、通常の生成、サンプリング、GPU 上の logits を変更しません。実装コメントも test only としています（`src/core/verify.cpp:3789-3830`）。

## 値と判定

形式は `m:bias` です。値全体を厳密に検証する parser ではなく、`std::sscanf(v, "%lld:%f", &m, &b) == 2` で2項目を読み、さらに `m > 0` を要求します（`src/core/verify.cpp:3820-3826`）。

| 値 | 結果 |
|---|---|
| 未設定 | `(0, 0)` となり無効 |
| 空文字、コロンがない値、2項目を変換できない値 | 無効 |
| `m <= 0`（例: `0:0.3`, `-2:0.3`） | 無効 |
| `7:0.3` | 有効。各行の token ID `0, 7, 14, ...`（`n_vocab_` 未満）の logit に `0.3f` を加算 |
| `m:bias` の後ろに余分な文字がある値 | 2項目の変換に成功すれば受理され、末尾は無視 |

`bias` は `float` として読みますが、追加の範囲・有限性チェックはありません。`m` は正の `long long` として読んで `int64_t` に格納されます。`m` が語彙数より大きくても、ループ開始値は 0 のため token ID 0 には加算されます（`src/core/verify.cpp:3822-3829`）。

## 有効になる条件

- `window_logprobs()` が呼ばれ、head logits・語彙数・対象行・出力先が有効であること。関数は `next_` がある場合は末尾の verifier に処理を委譲します（`src/core/verify.cpp:3789-3807`）。
- 生成側では、プロンプトを window で読む `STRATA_LOGPOS` 経路、または `STRATA_FOLLOW` と `STRATA_FOLLOW_LOGPOS` を併用する経路が該当します。通常のプロンプト処理は `logpos` が開けた場合だけ呼び出し、forced continuation 側は `fol` と `fol_lp` がある場合だけ呼び出します（`src/program/generate.cpp:16862-16865,16900-16913,18046-18073,19169-19179`）。
- `sycl/src/core/verify.cpp:2717-2767` にも同名の `window_logprobs()` がありますが、そこには `STRATA_FORCE_FAULT` の読み取り・加算がありません。この注入処理は `src/core/verify.cpp` の実装に限られます。

この変数は Strata の CLI オプションではなく、別の Strata 環境変数との優先順位もありません。補助ツール `tools/force_check.py` から使う場合、その子プロセス環境は親環境の `STRATA_*` を除去した後、設定ファイルの `env`、続いて `--env` 指定を重ねます。そのため、このツールでは `--env STRATA_FORCE_FAULT=7:0.3` が設定ファイル値より優先されます（`tools/force_check.py:51-62,123-128,157-186,352-354`）。このツール上の転送規則であり、Strata 本体の優先順位ではありません。

## 実行時の詳細

読み取りは `window_logprobs()` 内の関数ローカル `static const` 初期化子で一度だけ行われます。最初の呼び出し時に値を parse し、その後プロセス内で環境を書き換えても再評価されません（`src/core/verify.cpp:3820-3826`）。有効時は host 側の `h` 配列について、全 `T` 行で `v=0` から `n_vocab_` 未満まで `m` ずつ進み、該当要素へ bias を加算します。その後の argmax、対数確率、top-k の出力は変更後の `h` を使います（`src/core/verify.cpp:3810-3830,3831-3852,3855-3864`）。

この処理自身は有効・無効や parse 失敗をログに出しません。採点行は `window_logprobs()` の出力先へ書かれます。通常の `STRATA_LOGPOS` 経路で関数が失敗すると prompt 読み取りが失敗します。`STRATA_FOLLOW_LOGPOS` 経路では `strata serve: STRATA_FOLLOW_LOGPOS: <error>` を stderr に出します（`src/program/generate.cpp:16912-16913,19176-19179`）。fault 値を設定したこと自体による警告や終了はありません。

## 根拠

- `src/core/verify.cpp:3789-3816` — verifier 委譲、head logits の host コピーと有効性・コピー失敗条件。
- `src/core/verify.cpp:3817-3830` — test-only の説明、環境変数読み取り、形式判定、加算処理。
- `src/core/verify.cpp:3831-3864` — 加算後の行を使う argmax・対数確率・top-k 出力。
- `sycl/src/core/verify.cpp:2717-2767` — SYCL 版にはこの fault injection がないこと。
- `src/program/generate.cpp:16862-16913,18046-18073,19169-19179` — prompt / forced continuation の採点呼び出し条件とエラー観測。
- `tools/force_check.py:51-62,123-128,157-186,352-354` — 補助ツールから子プロセスへ環境を渡す順序。

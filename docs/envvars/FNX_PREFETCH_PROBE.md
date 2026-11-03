# `FNX_PREFETCH_PROBE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next split engine の診断用 probe を有効にします。各層の FFN 入力に次層の router を適用して expert の上位候補を推定し、次層で実際に選ばれた expert と照合して集計します。変数名に `PREFETCH` とありますが、ここで確認できる処理は予測精度や expert cache slot との重なりの計測であり、probe 自体が予測 expert を先読み・コピーする処理ではありません。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` を使います。値は `parse_whole()` で符号付き base-10 の `long long` 全体として解析されます。

| 設定 | 判定 |
|---|---|
| 未設定 | 既定値 `0` のため無効 |
| `0`, `+0`, `-0` | 無効 |
| 0 以外の有効な整数（例: `1`, `-1`, `+2`, `02`） | 有効 |
| 空文字、前後の空白、数字以外を含む文字列、`long long` の範囲外 | `std::runtime_error`。値を無効扱いにして続行する fallback はない |

先頭の `+` / `-` は受け付けますが、数字の後ろに文字があれば不正です。小数・真偽値の単語は受け付けません。大文字小文字の判定はありません。`FNX_PREFETCH_PROBE=0` は無効です。

## 有効になる条件

- `fnx::Engine` が作られる実行経路で参照されます。参照箇所は Flash-Next split engine の `src/split/src/engine.cu` にあり、この環境変数を読む他の箇所は見つかりませんでした。
- Engine の card 初期化ループ内で `c == 0` の場合だけ値を読みます。複数カードでも probe 用バッファは card 0 にのみ作られます。
- 対象の `Engine` で `enqueue()` の FFN 層処理が走ると probe が使われます。層 `l` の入力 `b.mixed` から層 `l + 1` の router logits と上位 `TOPK` 候補を計算し、層 `l + 1` の実際の選択と照合します。最終層には次層がないため予測しません。
- GPU backend のビルド差による値の判定分岐はこの箇所にはありません。ビルド・CLI によって split Engine 自体が使われない場合、この変数の効果もありません。
- RAM expert cache が稼働している場合、`probe_cnt` があると `router_route()` に cache 計画先を渡さず、その後 `moe_cache()` に計画を回します。従ってこの場合は集計だけでなく、cache 計画の実行箇所も変わります。cache が稼働していない場合はこの計画差はありません。
- CLI 引数による上書きは見つかりませんでした。

## 実行時の詳細

値は `Engine` の生成時、card 0 のバッファ初期化で都度評価されます。関数内 `static` などのキャッシュはなく、同じプロセスで後から別の `Engine` を生成すればその生成時の環境値が読まれます。既に生成された Engine のバッファ有無は変わらないため、生成後に環境を変更してもその Engine には反映されません。子プロセスへの転送・上書き処理はこの変数について確認できませんでした。

有効時には card 0 に logits、予測 index、7 個のカウンタ用 device buffer を確保します。これらの buffer は `dalloc()` によりゼロ初期化されます。各 FFN 層で probe は次層 router を `b.mixed` に適用し、各行について router logits の上位 `TOPK` expert を推定します。次層では選択済み expert と推定値を重複なしで数え、RAM slot 情報があれば slot にない選択・推定も集計します。

7 カウンタは順に、layer-window ごとの実選択 expert 数、推定 expert 数、両方に含まれる数、layer-window 数、slot にない実選択数、slot にない実選択のうち推定にも含まれる数、slot にない推定のうち実選択には含まれない数です。実選択数は router の上位 `TOPK` 全件ではなく、同一 window 内の distinct expert 数です。

`Engine::probe_counts()` は集計値を host にコピーします。`fnx_run` は計測結果の出力時に layer-window 数が 1 以上の場合、stdout に `prefetch probe: ...` を出力します。RAM slot 関連の値がある場合は `prefetch probe, experts in RAM: ...` も出力します。probe が無効なら空の結果となり、この表示は行われません。Engine 初期化時の専用ログはありません。

不正値は whole-number parser の例外、device buffer 確保失敗は `cudaMalloc of ...` を含む `std::runtime_error` になります。有効値で probe の kernel 起動や集計コピーに失敗した場合も、通常の CUDA error check 経由で失敗します。

## 根拠

- 値の読取と card 0 限定のバッファ確保: `src/split/src/engine.cu:188-192`。
- 整数全体の parse、unset 時の既定値、flag の判定、不正値の例外: `src/split/src/env.hpp:15-21,33-40,51-52`。
- device buffer のゼロ初期化と確保失敗: `src/split/src/engine_parts.hpp:50-68`。
- 次層 router の予測、実選択との採点、および probe 有効時の cache 計画経路: `src/split/src/engine.cu:905-925`。
- 予測値の集計内容: `src/split/src/kernels.cu:1755-1784`。
- host への集計値取得: `src/split/src/engine.cu:654-660`。
- `fnx_run` の stdout 表示条件と文言: `src/split/tools/fnx_run.cpp:1136-1143`。
- 候補一覧には `FNX_PREFETCH_PROBE` が載っています（`docs/envvars/000_envvers.md:590`）。Strata ソースでは上記の `env_flag()` 呼び出しで実際の環境値読取を確認しました。

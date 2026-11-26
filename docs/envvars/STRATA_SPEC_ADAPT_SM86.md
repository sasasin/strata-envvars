# `STRATA_SPEC_ADAPT_SM86`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の compute capability 8.6（sm_86）で、投機生成中の expert tier 適応を起動直後だけ速めるための opt-in です。この変数自体は `STRATA_SPEC_ADAPT_EVERY=2` と `STRATA_SPEC_ADAPT_WARM=200` を、まだ設定されていない場合にプロセス環境へ補います。実際に生成設定へ取り込まれるのは `--spec >= 2` の実行であり、最初の 200 verify rounds は 2 rounds ごと、その後は通常の適応間隔になります。適応処理は使用頻度に応じて VRAM 上の expert を入れ替える機能です（`engine/src/core/nv_defaults.cpp:328-347`、`engine/src/program/generate.cpp:1045-1051,5100-5109,22055-22059`）。

## 値と判定

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `apply_spec_adapt_default` が呼ばれる CUDA 起動経路 | 既定で無効。追加設定をしない | 値の先頭バイトが文字 `'1'`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `-1` など、先頭が `'1'` でない値 |
| `STRATA_SM86_PERF`（有効値判定後の追加条件） | 無効化しない | 先頭バイトが `'0'` でない場合は続行 | 先頭バイトが `'0'`（例: `0`, `0anything`）なら追加設定しない |

対象変数は `getenv` で取得し、文字列全体の比較や数値変換をせず、先頭文字だけを検査します。大文字小文字や後続文字は判定に関与しません。未設定と空文字はいずれも無効です。`STRATA_SM86_PERF` も共通 helper `off` が先頭文字 `'0'` のみを見ます（`engine/src/core/nv_defaults.cpp:15-18,328-339`）。

補助変数の既定値はそれぞれ `2` と `200` です。既に環境に存在すれば、値が空や不正でも書き換えません。その後の生成側は `STRATA_SPEC_ADAPT_EVERY` を `atoi`、`STRATA_SPEC_ADAPT_WARM` を `atoll` で読みます。warm-up 間隔 `n` が正で現在の `o.adapt_every` より小さく、round 数 `wr` が正のときだけ採用します。従って補助変数が空・非数値なら変換結果は 0 となり採用されず、`2tail` は 2、`200tail` は 200 として扱われます。`--adapt-every` が明示された場合はこの環境変数読み取りブロック自体を通りません（`engine/src/program/generate.cpp:1047-1051,4058,5104-5109`）。

## 有効になる条件

- 起動時に CUDA デバイスが 1 台以上見つかり、全ての可視 CUDA デバイスの compute capability が同じで、その値が 8.6 であること。混在 compute capability の複数 GPU では適用関数が呼ばれません（`engine/src/program/generate.cpp:4421-4450`）。
- HIP と Metal ではこの NVIDIA 設定処理を含むコンパイル経路に入りません（`engine/src/program/generate.cpp:4421-4426`）。
- `STRATA_SM86_PERF` の値が `'0'` で始まらないこと。`STRATA_SM86_PERF=0` などの場合は本変数が有効値でも補助変数を設定しません（`engine/src/core/nv_defaults.cpp:337-345`）。
- 通常の CLI 生成処理で `--spec >= 2` かつ `--adapt-every` 未指定であること。`--spec` が 0 または 1 なら生成側の warm-up 読み取りを通りません。`--adapt-every` の明示値は優先されます（`engine/src/program/generate.cpp:4040,4058,5104-5109`）。
- 適応機能を実行するには、expert が全て GPU cache に常駐しておらず、GPU cache slot があり、`o.adapt_every > 0` かつ `o.adapt_swaps > 0` であることが必要です。これを満たさなければ使用量追跡や入れ替え処理は開始されません（`engine/src/program/generate.cpp:14948-15002`）。
- `STRATA_ADAPT_MID` を含む coverage ベースの adaptive defaults が適用される構成では、CLI 未指定の `o.adapt_every` が後段で 2 に変更されることがあります。その場合、設定された warm-up 間隔も 2 なので warm-up の間隔による差はなくなります（`engine/src/program/generate.cpp:14943-14964,24558-24568`）。
- `STRATA_SPEC_ADAPT_EVERY` または `STRATA_SPEC_ADAPT_WARM` が既に設定済みなら、その値を本変数による既定値は上書きしません。空文字も「設定済み」です（`engine/src/core/nv_defaults.cpp:339-346`）。

## 実行時の詳細

起動時、CUDA のデバイス情報を確認した後、同一 compute capability の場合に `apply_spec_adapt_default` が呼ばれます。そこで対象環境変数を一度読み、条件に合えば不足している補助変数だけを `_putenv_s`（Windows）または `setenv(..., 0)`（その他）で設定します。環境を変更する処理は成功時もログを出しません（`engine/src/program/generate.cpp:4427-4449`、`engine/src/core/nv_defaults.cpp:328-347`）。

生成引数の処理後、`--adapt-every` が未指定で `--spec >= 2` なら補助変数を読みます。`o.adapt_iv(rounds)` は round が `adapt_warm_rounds` 未満の間 `adapt_warm_every`、それ以降は `adapt_every` を返し、適応判定で verify round ごとに使われます（`engine/src/program/generate.cpp:1047-1051,5104-5109,22055-22059`）。対象変数は static cache されず、プロセス起動時に一度判定されます。補助変数は起動時に設定され、引数処理時に一度読み込まれます。

## ログと測定値

対象変数の有効・無効や補助変数の設定を直接示すログはありません。適応 tier が実際に動く場合はモードに応じて `strata serve: adaptive tier: blocking, ...` または `strata serve: adaptive tier asynchronous (--adapt-async 1): ...` の行が出ますが、この行だけでは本変数が有効だったことは判別できません（`engine/src/program/generate.cpp:15600-15613`）。本変数による終了・エラー経路は確認できません。ソースコメントには過去の A/B 言及がありますが、実装上の効果の保証や一般化可能な測定値としては記載しません。

## 根拠

- `engine/src/core/nv_defaults.cpp:15-18,328-347` — off 判定、sm_86 条件、対象変数の読み取り、補助環境変数の既定値と上書き規則。
- `engine/src/program/generate.cpp:4421-4450` — CUDA 起動時の同一 compute capability 判定と適用関数の呼び出し。
- `engine/src/program/generate.cpp:1045-1051,4040-4058,5100-5109,22055-22059` — CLI 優先、補助値の変換、warm-up 間隔と適応判定。
- `engine/src/program/generate.cpp:14948-15002,15600-15613` — expert cache 状態による適応処理の条件と観測可能なログ。

# `STRATA_LM_PREFETCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

layer-major prefill の各層で、ルーティング結果が出る前に、その層の非 resident・非 pinned expert の読み込みジョブを stager に開始するかを制御します。既定では有効です。有効時は GPU の attention / router 処理中に expert のホスト側読み込みを進め、ルーティングで使わなかった expert のジョブは skip します。無効時はルーティング後に必要な expert だけのジョブを開始します。

この変数は layer-major prefill の expert staging にだけ関係します。通常の chunk-major prefill や、layer-major prefill が選ばれない実行では効果がありません。

## 値と判定

値全体の parse や数値変換はせず、`std::getenv()` が返す文字列の先頭文字だけを検査します。結果は `static const bool` に保存されます。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（設定値の先頭が `\0` であり、`'0'` ではない） |
| 先頭文字が `0` | 無効。`0` や `0anything` が該当 |
| それ以外 | 有効。例: `1`, `true`, `false`, `anything` |

空白除去、大文字小文字変換、文字列全体の真偽値判定はありません。`false` も有効です。無効値に対するエラーや警告、fallback はありません。

## 有効になる条件

環境変数が有効と判定されても、layer-major prefill が実行されなければ読み込み方式は変わりません。

- Metal の `Prefill::run()` は Metal engine の経路から戻るため、この staging 判定には到達しません。
- CUDA では `STRATA_PREFILL_LAYER_MAJOR` の解決結果が on である必要があります。unset 時の既定はビルド・モデル条件に依存し、CUDA layer split などに限られます。`STRATA_PREFILL_LAYER_MAJOR=0` や `STRATA_DEFAULTS=026` などで layer-major が off なら、この変数は使われません。
- HIP ビルドでは layer-major 自体が既定 off で、`STRATA_PREFILL_LAYER_MAJOR` の解決に加え `STRATA_LM_HIP=1` が必要です。`STRATA_LM_HIP` が無効なら `lm_prepare()` が layer-major を拒否します。
- `lm_prepare()` が image prompt、peer GPU、未対応の layer split / PLE 配置、DFlash2 prompt taps、`STRATA_KVA`、chunk 境界で yield する batch read、`--prefill-pipe`、未対応 expert format、短い prompt、VRAM 不足などを検出すると layer-major を開始しません。該当時は通常の `run_impl()` に進みます。
- レイヤーの expert source `m.src` が null の場合、`lm_prefetch()` は何も開始せず成功を返します。cache resident または pinned の expert も事前読み込み対象から除外されます。

この変数自体には CLI 引数や別環境変数による上書き処理はありません。ほかの変数・条件は layer-major 経路へ入るかどうかを左右します。

## 実行時の詳細

`STRATA_LM_PREFETCH` は `run_layer_major()` の実行がこの判定箇所に初めて到達したときに読み取られます。判定値はプロセス内で cache されるため、その後の環境変更は反映されません。

有効時、各層の処理開始時に全 expert を走査し、host cache に resident でなく pinned でもない expert を stager の job にします。source が transient か、安定した blob pointer を得られない場合は source にコピーを依頼する job、それ以外は blob pointer を使う job を登録します。stager を開始した後、ルーティング結果で使われない job は skip され、使われる job は staging buffer から GPU へ転送されます。

無効時は層の attention / router 後に routed expert の一覧を作り、resident / pinned でないものだけの job を開始します。そのため、層の処理と並行した全候補の先行読み込みは行われず、未使用 expert の読み込みも要求しません。

この変数専用のログはありません。layer-major が実行された場合、stderr に `strata prefill: layer-major ...` の集計（stream した blob 数や時間など）が出ますが、そのログから `STRATA_LM_PREFETCH` の判定値そのものは分かりません。layer-major が選択されない場合は、理由に応じて `strata prefill: layer-major off for this prompt: ...` が出ることがあります。stager の source copy が失敗すると `prefill: the expert source could not copy experts ...` を stderr に出して abort します。

## 根拠

- 値判定、既定値、cache、stager job 作成: `src/prefill/prefill.cpp:6354-6379`。
- routed expert の抽出、未使用 job の skip、無効時に routed expert のみを開始する分岐: `src/prefill/prefill.cpp:6404-6444`。
- staged expert の待ちと GPU 転送: `src/prefill/prefill.cpp:6545-6573`。
- layer-major 自体の backend / prompt / model / resource 条件: `src/prefill/prefill.cpp:5955-6061`。
- CUDA/HIP での layer-major 呼び出し、HIP 条件、off 時の通常経路とログ: `src/prefill/prefill.cpp:7222-7271`。
- stager thread の source copy 失敗時の stderr と abort: `src/prefill/prefill.cpp:643-698`。
- layer-major と staging の概要、および layer-major 有効時の stderr 集計: `src/prefill/prefill.cpp:5875-5892,7150-7182`。

`docs/DETAILS.md` には `STRATA_LM_PREFETCH` 固有の説明や測定値は見つかりませんでした。ここではソースから確認できる処理のみを記載しています。

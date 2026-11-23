# `STRATA_LM_HIP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

AMD/HIP ビルドで layer-major prefill の実行を許可する opt-in です。これを有効にしても layer-major 経路自体は選択されません。別の `STRATA_PREFILL_LAYER_MAJOR` の判定で経路が選ばれた後、`Prefill::lm_prepare` がこの変数を確認し、無効なら準備を断って通常の chunk-major prefill に戻します（`engine/src/prefill/prefill.cpp:8166-8178,9652-9705`）。

この読み取りは `STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義されたビルドに限られます。それ以外のビルドではこの変数を読みません（同:8169-8179）。

同梱の `terminal/tools/par/recon3.py` は、特定の HIP replica benchmark arms 用に `STRATA_LM_HIP=1` を `--env` 引数として組み立てます。これはツールからの設定値の転送であり、このスクリプト自体は値を読み取って分岐しません（`terminal/tools/par/recon3.py:28-45,48-57`）。

## 値と判定

`std::getenv` の結果が null でなく、先頭バイトが文字 `'1'` なら有効です。文字列全体の比較や数値変換はしません。したがって `1`、`10`、`1anything` は有効、未設定・空文字・`0`・`0anything`・`2`・`true`・` 1`・`+1` は無効です。大文字小文字や後続文字は判定に関係しません（`engine/src/prefill/prefill.cpp:8172-8177`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_USE_HIP` または `STRATA_HIP_GFX906` 定義あり | 無効。layer-major 準備を断る | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `2`, `true`, ` 1`, `+1` |
| どちらの macro も定義なし | この変数は読まれない | 該当なし | 該当なし |

## 有効になる条件

- ビルドが `STRATA_USE_HIP` または `STRATA_HIP_GFX906` の経路に入ること。この条件を満たさないビルドでは変数は参照されません（`engine/src/prefill/prefill.cpp:8169-8179`）。
- layer-major 経路が別途選択されること。`STRATA_PREFILL_LAYER_MAJOR` が空でない場合、`prefill_layer_major_resolve` は `std::atoi(env) != 0` で判定し、明示値を既定値より優先します。たとえば `1` や `1tail` は on、`0` や `0tail` は off、`true` や数値に変換できない文字列は `atoi` の結果が 0 なので off です。未設定または空文字では既定値を使いますが、現行の既定値は HIP を含む全条件で off です。よって `STRATA_LM_HIP=1` 単独では layer-major は始まりません（`engine/include/strata/core/sm120_series.hpp:176-191`、呼び出しは `engine/src/prefill/prefill.cpp:9652-9661`）。
- 自動で layer-major を設定する small-card prompt 経路は HIP では適用されません。同経路の判定は `hip` が true なら直ちに何も選ばず、`STRATA_PREFILL_LAYER_MAJOR` がユーザー設定済みの場合も上書きしません（`engine/include/strata/core/sm120_series.hpp:195-218`、呼び出し側は `engine/src/program/generate.cpp:12483-12511`）。
- 変数が有効でも、準備時に layer split の hand-off / peer GPU、対応していない画像 prompt・KVA・chunk 境界 yield・`--prefill-pipe`、ビルド済み expert-nibble、routing/row debug dump、必要なバッファや VRAM / pinned RAM の不足などがあると layer-major は decline します。失敗理由を出して通常の `run_impl` に進む経路があります（`engine/src/prefill/prefill.cpp:8180-8234,8273-8339,9684-9705`）。

## 実行時の詳細

`STRATA_LM_HIP` は `Prefill::lm_prepare` 内の関数ローカル `static const bool` として遅延初期化されます。最初に layer-major の準備が呼ばれた時に一度読み、そのプロセス内では値を cache します。そこまでに環境が変更されれば初回読み取りには反映され得ますが、初回評価後の変更は反映されません。layer-major の選択判定は `STRATA_PREFILL_LAYER_MAJOR` を別の関数ローカル static で読むため、こちらも初回評価後は cache されます（`engine/src/prefill/prefill.cpp:8082-8086,8166-8178,9657-9661`）。

HIP ビルドで `STRATA_LM_HIP` が無効だと、`lm_prepare` は理由 `layer-major prefill has only been run on NVIDIA CUDA` を返して準備を中止します。通常の `run` はその理由で layer-major を見送り、chunk-major の `run_impl` を実行します。`run_multi` は準備失敗を `prefill: multi-prompt read declined: ...` として返します（`engine/src/prefill/prefill.cpp:8173-8177,8413-8424,9694-9705`）。

有効化され準備も通れば layer-major walk が実行されます。これは layer ごとに super-chunk を処理し、各 layer の streamed experts を super-chunk 内でまとめて読む経路です。従来経路と expert の加算順・MMQ の row grouping が異なることはソースに記載されています（`engine/src/prefill/prefill.cpp:8066-8080`）。`STRATA_LM_HIP` 自身は chunk サイズ、VRAM/host 配置、または CLI 設定に優先値を与えません。

## ログと測定値

通常の `run` で layer-major が選択され、HIP opt-in が無効なら、準備の失敗理由が次の stderr 行に含まれます（理由ごとに同じ行の再出力を抑制します）。

```text
strata prefill: layer-major off for this prompt: layer-major prefill has only been run on NVIDIA CUDA
```

準備失敗時は理由が同一の間この行を毎回は出さず、長い prompt で 16 回連続して decline した時に継続状況の行も出ます。準備成功時は `strata prefill: layer-major (...)` の統計行が stderr に出ます（`engine/src/prefill/prefill.cpp:9567-9574,9694-9703`）。

`docs/DETAILS.md` にこの変数の記載はありません。`docs/SETTINGS.md:152` は値を `on / off` と分類していますが、実装は on/off の語を parse せず、先頭文字 `'1'` のみを受け付けます。ソースコメントは `gfx1201` を qualification 中と述べていますが、`STRATA_LM_HIP` による有効化がどの AMD 機種で正確性・性能確認済みかを示す測定値は、この commit のソースと資料から確認できません（`engine/src/prefill/prefill.cpp:8170-8173`）。

## 根拠

- `engine/src/prefill/prefill.cpp:8166-8179` — HIP build guard、変数の読み取りと拒否理由。
- `engine/src/prefill/prefill.cpp:8082-8086,9652-9705` — layer-major の別選択条件、cache、fallback と診断ログ。
- `engine/include/strata/core/sm120_series.hpp:176-191` — layer-major の unset default と `STRATA_PREFILL_LAYER_MAJOR` の parse。
- `engine/include/strata/core/sm120_series.hpp:195-218` — small-card 自動選択が HIP では無効である条件。
- `engine/src/prefill/prefill.cpp:8180-8234,8273-8339` — layer-major 準備の適用条件と失敗経路。
- `engine/src/prefill/prefill.cpp:9567-9574` — layer-major 成功時の stderr 統計行。
- `terminal/tools/par/recon3.py:28-45,48-57` — HIP replica benchmark arms への環境値引数。

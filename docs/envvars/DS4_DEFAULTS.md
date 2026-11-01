# `DS4_DEFAULTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で変更なし。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジンで、Strata 0.2.7 で変更された複数の既定値を 0.2.6 相当に戻すマスター切替です。`src/dsv41/ds4_experts_rule.hpp` の `defaults_026()` が値を読み、各機能の既定値決定関数へ bool を渡します。単一の実行モードを直接切り替える値ではなく、対象となる既定値を個別に選び直します。Qwen 用の別変数 `STRATA_DEFAULTS` とは別です（`src/dsv41/ds4_experts_rule.hpp:16-27`; `docs/release-notes-0.2.7.md:30-35`）。

## 値と判定

値は数値変換せず、文字列全体を `strcmp` で比較します。

| 環境値 | `defaults_026()` | 判定 |
|---|---:|---|
| 未設定 | false | 新しい既定値側 |
| `026` | true | 0.2.6 相当の既定値側 |
| `0.2.6` | true | 同上 |
| `v0.2.6` | true | 同上 |
| 空文字、`1`、`true`、`026 `、大文字・小文字違いなど | false | 新しい既定値側 |

認識するのは上表の 3 文字列との完全一致だけです。空白除去、大小文字変換、数値 parse、無効値の警告や別値への fallback はありません。結果は `defaults_026()` 内の `static const bool` に保存され、プロセスで最初に呼ばれた時点の値が以後使われます。したがって、その後の環境値変更は反映されません（`src/dsv41/ds4_experts_rule.hpp:22-27`）。

## 有効になる条件

変数判定そのものに OS / GPU / build 条件はありません。一方、渡された bool が変える各既定値には機能固有の条件があります。対象は DeepSeek V4.1 エンジンのコードで、特に次のような分岐に作用します。

| 既定値 | `DS4_DEFAULTS` が認識値の場合の選択 | 条件・個別指定 |
|---|---|---|
| 1 語あたりの expert 数 | 2 枚以上の RDNA4 GPU が半数以上の routed experts を保持することを理由に 5 experts にする既定判定を無効化。小容量 GPU（合計 VRAM 16 GiB 以下）や統合 GPU に対する既定判定は残る | `--experts N` が指定されればその数を使い、モデルの expert 数を上限にする。`DS4_TOPK` はテスト用上書き（`src/dsv41/ds4_experts_rule.hpp:30-46`; 呼び出し `src/dsv41/ds4_model.cu:2361-2380`） |
| prompt chunk | `multi_tp` 条件を既定 chunk の 1024 行選択から除外する | 適応には chunked prompt が使われる必要がある。`--prefill-chunk N` が明示されるとルール値より優先し、`DS4_CHUNK` が設定されるとさらにその値で置き換える（`src/dsv41/ds4_experts_rule.hpp:64-80`; `src/dsv41/ds4_model.cu:2282-2303`） |
| staging ring | GPU が保持する expert share が `1/1.3` 以上なら 16 MB、それ未満なら 400 MB | `ring_mb_auto()` が呼ばれる経路の自動値。`DS4_RING_MB` 指定時は別の値を使う（`src/dsv41/ds4_experts_rule.hpp:146-155`; 呼び出し `src/dsv41/ds4_model.cu:3283-3298,3409`） |
| attention slab | 統合 GPU でも base は 8 MB。`DS4_ATTN_SLAB` 未設定時は base に固定し、自動拡張しない | `STRATA_DS4_A_MB` が非 0 なら base を明示し、`DS4_ATTN_SLAB` の非負値指定も優先する。正値は行数要求、0 は base（`src/dsv41/ds4_experts_rule.hpp:102-130,167-172`; `src/dsv41/ds4_model.cu:3317-3354`） |
| CPU lane の RAM コピー pin | 未設定なら OFF | `DS4_COPY_PIN` の明示値が優先。pin 実行には RAM copy chunk も必要（`src/dsv41/ds4_experts_rule.hpp:174-180`; `src/dsv41/ds4_model.cu:5140-5158`） |
| huge-page copy arena | 未設定なら OFF | `DS4_COPY_HUGETLB` の明示値が優先（`src/dsv41/ds4_experts_rule.hpp:182-187`; `src/dsv41/ds4_model.cu:4973-4985`） |
| matrix-core attention | 未設定なら OFF | `DS4_FAST_ATTN` の明示値が優先する。未設定時の通常既定は HIP の gfx1200 / gfx1201、および Windows HIP の gfx1151 に限られる。CUDA はこの機能の自動選択をしない（`src/dsv41/ds4_experts_rule.hpp:189-195`; `src/dsv41/ds4_kernels.cu:2077-2090`） |
| drafter の累積 confidence cut | 未設定時 0 | `STRATA_DS4_DSPARK_CUM` が設定されていればその値が優先。未設定時の通常 0.5 既定は gfx1200 / gfx1201 に限られる（`src/dsv41/ds4_experts_rule.hpp:197-200`; `src/dsv41/ds4_main.cpp:169-180`） |
| RAM store spare slots / put-back | 未設定なら両方 OFF | `DS4_STORE_SPARE` と `DS4_STORE_PUT` の個別指定を優先（`src/dsv41/ds4_experts_rule.hpp:203-208`; 呼び出し `src/dsv41/ds4_model.cu:5550-5557,7113-7121`） |
| RAM store の prompt 後 preload | `DS4_SETTLE_STORE` 未設定時は ON | 明示値は `env_f()` で float に変換して使用。copy mode では 0.2.6 相当の分岐は RAM copy にある expert を preload 対象から除外しない（`src/dsv41/ds4_experts_rule.hpp:210-213`; `src/dsv41/ds4_model.cu:7179-7194`） |
| dense dequantizer | 未設定なら旧 row-per-lane kernel | `DS4_DQ_OLD` の非空値があれば `atoi != 0` の結果が優先。未設定で通常時は HIP gfx11 のみ旧 kernel（`src/dsv41/ds4_experts_rule.hpp:215-220`; `src/dsv41/ds4_iq.cu:1398-1422`） |
| head の列数 / drafter head と gate-up operand | GGUF head は 4 列ずつ。markov head を Q8 にせず F16 で読み、gate/up は F16 activation copy を使わない | `DS4_HEAD_PER` は指定時に列数を上書きする。markov head の変更は drafter head が存在する場合、gate/up は該当計算経路で適用（`src/dsv41/ds4_experts_rule.hpp:222-227`; `src/dsv41/ds4_model.cu:4203-4209,4402-4411,9621-9634`） |
| RDNA3 dense prefill GEMM | 未設定なら無効 | HIP build の GEMM 経路だけにあり、`STRATA_DENSE_PFGEMM` の明示値が優先する。CUDA build にはこの kernel 選択分岐がない（`src/dsv41/ds4_experts_rule.hpp:228-232`; `src/dsv41/ds4_model.cu:3435-3455`） |

`DS4_DEFAULTS` が false でも、それだけで上記機能がすべて ON になるわけではありません。個別の backend / GPU / モデル状態 / RAM store や chunked prompt の有無に応じて各規則が判断します。反対に true でも、呼び出し箇所の条件が成立しない機能は使われません。

## 実行時の詳細

ソース全体の完全一致検索では、環境から `DS4_DEFAULTS` を直接読む実装は `defaults_026()` の `std::getenv` 1 箇所です。そこから DeepSeek V4.1 の各規則へ bool が渡されます。`ds4_model.cu` の model 初期化では expert 数、prompt chunk、staging ring、attention slab、copy arena、store 等の選択に使われ、kernel / drafter 側でも dequantizer、attention、head の既定選択に使われます。別の helper や動的な環境変数名経由で `DS4_DEFAULTS` を再読する箇所は見つかりませんでした（`src/dsv41/ds4_experts_rule.hpp:25-27`; 主な呼び出し `src/dsv41/ds4_model.cu:2293,2372,3294,3331,3354,3445,4208,4409,4978,5144-5145,5551,5567,7113,7182,7191,9629`; `src/dsv41/ds4_iq.cu:1402-1406`; `src/dsv41/ds4_kernels.cu:2077-2090`; `src/dsv41/ds4_main.cpp:176-180`）。

関連する個別 env は一般に優先されます。たとえば、`copy_pin_default()` / `copy_hugetlb_default()` / `fast_attn_default()` は未設定を表す `env < 0` の場合にだけ `v026` の既定を適用し、明示値があればそれを先に返します。`env_tri()` は未設定を -1、設定値を `atoi(v) != 0` による 0 / 1 にし、空文字は 0 として扱います（`src/dsv41/ds4_model.cu:97-101`; `src/dsv41/ds4_experts_rule.hpp:174-194`）。CLI も `--experts` と `--prefill-chunk` の明示値を各既定規則より先に採ります（`src/dsv41/ds4_experts_rule.hpp:39-46,64-80`; `src/dsv41/ds4_model.cu:2293-2299,2372-2378`）。

`DS4_DEFAULTS` 自体の専用ログはありません。下流の条件によって stderr に expert 数（`src/dsv41/ds4_model.cu:2374-2378`）、自動 chunk（同 `2295-2297`）、verbose 時の staging ring（同 `3295-3297`）、copy pin の成功・失敗（同 `5146-5158`）などが出ることはありますが、これらは選ばれた処理や条件のログで、変数名や parse エラーを通知するものではありません。ソース上、`DS4_DEFAULTS` 自体が終了やエラーを発生させる分岐はありません。

Strata のアプリ設定では「DeepSeek speed-ups」を OFF にした構成として `DS4_DEFAULTS=026` と 6 個の個別変数を同時に設定します。ON ではその 7 項目を除去します。このため、アプリの OFF 動作にはマスター値だけでなく明示的な個別値も含まれます（`apps/host/server/native-settings.mjs:49-53`; `strata_control/speed_switches.py:48-55`）。

## 根拠

- 読み取り・完全一致値・cache: `src/dsv41/ds4_experts_rule.hpp:22-27`。
- 変更対象の一覧と明示値優先の設計: `src/dsv41/ds4_experts_rule.hpp:16-21`。個々の現行判定は同ファイルの `39-80,102-130,146-155,167-232`。
- 呼び出しと下流動作: `src/dsv41/ds4_model.cu:2282-2303,2361-2380,3283-3298,3317-3354,3435-3455,4198-4214,4398-4411,4973-4990,5138-5158,5550-5579,7109-7121,7179-7200,9621-9634`; `src/dsv41/ds4_iq.cu:1398-1435`; `src/dsv41/ds4_kernels.cu:2077-2090`; `src/dsv41/ds4_main.cpp:169-180`。
- 文書との照合: `docs/release-notes-0.2.7.md:30-35` は切替の概要・0.2.6 相当へ戻す対象・アプリでの設定を説明し、ソースの一覧およびアプリ設定と一致します。測定値は本変数による全機能の効果として一般化せず、本調査文書には記載していません。

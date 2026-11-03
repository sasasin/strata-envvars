# `DS4_DEFAULTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 エンジンで、0.2.7 で変わった複数の既定動作を 0.2.6 相当へ戻す互換スイッチです。モデルや CLI の実行モードを直接選ぶ値ではなく、エンジンが個々の既定値を決める際に参照します。対象には prompt chunk、attention slab、CPU lane のコピー、expert 数、RAM store、dequantizer、head などがあります。Qwen の既定値を切り替える `STRATA_DEFAULTS` とは別です（`src/dsv41/ds4_experts_rule.hpp:16-26`）。

## 値と判定

値は数値変換せず、文字列全体を大文字小文字も含め完全一致で比較します。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | 無効 | 現行の既定値を使う |
| `026`、`0.2.6`、`v0.2.6` | 有効 | 対象となる既定値を 0.2.6 相当に戻す |
| 空文字、`0`、`027`、`026 `、`V0.2.6` など | 無効 | 現行の既定値を使う |

無効な文字列への警告やエラーはありません。読み取り結果は `defaults_026()` 内の `static const bool` に保存されるため、最初の呼び出し後にプロセス環境を書き換えても反映されません（`src/dsv41/ds4_experts_rule.hpp:22-27`）。

## 有効になる条件

DeepSeek V4.1 のコードがビルドされ、そのエンジン経路で該当する既定値が評価される場合にだけ作用します。すべての実行で全項目が一律に変更されるわけではありません。GPU/OS、VRAM と expert の配置、モデル形式、prompt が chunk 化されるか、RAM store や drafter の使用状態など、それぞれの機能条件に従います。

この値を有効にした場合、主に次の既定値が 0.2.6 相当に戻ります（`src/dsv41/ds4_experts_rule.hpp:16-21,43-50,80-97,133-147,162-170,183-247`）。

- staging ring は expert share が `1/1.3` 以上なら 16 MB、それ未満なら 400 MB の固定値になります。
- prompt chunk の現行ルールにある RDNA4 の multi-TP 向け 1024 行分岐は適用されません。明示した `--prefill-chunk N` は優先されます。
- `DS4_ATTN_SLAB` が未設定なら slab の自動拡張を止め、base を使います。明示値は優先されます。attention base の既定は 8 MB 相当です（`STRATA_DS4_A_MB` が明示されていればそちらが使われます）。
- `DS4_COPY_PIN` と `DS4_COPY_HUGETLB` が未設定なら無効です。各変数の明示値は優先されます。
- `DS4_FAST_ATTN` が未設定なら無効です。明示値は優先されます。既定機能は GPU/backend 条件にも依存し、HIP の gfx1200/1201、および Windows HIP の gfx1151 以外へ暗黙に有効化するものではありません。
- `STRATA_DS4_DSPARK_CUM` が未設定なら drafter の cumulative cut は 0 です（現行既定で gfx1200/1201 のみ使う 0.5 にはなりません）。明示値は優先されます。
- `--experts` が未指定のとき、RDNA4 1 枚または複数枚に対する現行の faster-mode 既定判定を無効にします。小容量 GPU / 統合 GPU の 5 experts 既定は残ります。`--experts N` は優先されます。
- `DS4_STORE_SPARE` と `DS4_STORE_PUT` が未設定なら無効です。明示値は優先されます。
- `DS4_SETTLE_STORE` が未設定なら prompt 後の RAM store preload を有効に戻します。明示値は優先されます。
- 対象経路の dense dequantizer は旧 row-per-lane kernel、head の処理列数は 4、drafter の Markov head は F16、gate/up operand は F32 相当の既定になります。`DS4_HEAD_PER` は明示値で上書きできます。HIP gfx11 の dequantizer は別条件です（後述）。
- `STRATA_DENSE_PFGEMM` が未設定なら RDNA3 の WMMA dense GEMM は無効です。明示値は優先されます。

## 実行時の詳細

エンジンが `defaults_026()` を最初に呼んだ時点で環境変数を一度読みます。主な呼び出し元はモデルロード時の prompt chunk、expert 数、staging ring、attention slab、コピー arena、store 設定、および head 設定です（`src/dsv41/ds4_model.cu:2788,2877,3943,4070-4093,5861,6027,6677,6693,8657,8727,13291-13298`）。GPU 状態やモデル状態によって呼び出し自体が無い機能もあります。

各機能の明示設定との優先順位は機能ごとに異なります。たとえば `--experts` と `--prefill-chunk` はスイッチ由来の既定値より先に選ばれます。一方、環境変数を読む機能ではその明示値が既定値関数の引数として先に判定されます。dequantizer は HIP gfx11 で特別扱いされ、`DS4_DEFAULTS` だけでは旧 kernel を選びません。gfx11 では `DS4_DQ_OLD=1` が必要で、対応する型に限られます（`src/dsv41/ds4_experts_rule.hpp:43-50,80-89,192-210,221-247`; `src/dsv41/ds4_iq.cu:1436-1463,1465-1473`）。

この変数そのものを受理・拒否した旨のログは見つかりません。個別機能の既存ログは条件付きで出ます。たとえば attention slab の自動拡張ログは verbose 時のみであり、0.2.6 相当で自動拡張されない場合は出ません（`src/dsv41/ds4_model.cu:4094-4103`）。prompt chunk の選択など、機能ごとの別ログは `DS4_DEFAULTS` の判定結果を直接表示するものではありません。値が未対応でも起動失敗にはならず、単にスイッチが無効になります。

Strata の release notes も、この変数を DeepSeek の既定値を戻すスイッチとして挙げ、個別設定が優先すると記しています（`docs/release-notes-0.2.7.md:28-35`）。測定値はこの文書では引用せず、実行時の性能や数値同一性を独自に検証したものではありません。

## 根拠

- `src/dsv41/ds4_experts_rule.hpp:16-27` — スイッチの役割、許容文字列、完全一致判定、static cache。
- `src/dsv41/ds4_experts_rule.hpp:43-50,80-97,133-147,162-170,183-247` — 各既定値と個別設定の優先規則。
- `src/dsv41/ds4_model.cu:2788,2877,3943,4070-4103,5861,6027,6677,6693,8657,8724-8747,13291-13298` — 実行経路、既定値の利用、関連ログ。
- `src/dsv41/ds4_iq.cu:1436-1463,1465-1473` — gfx11 の dequantizer 例外と kernel 選択。
- `src/dsv41/ds4_main.cpp:233-244` — drafter の cumulative cut と明示値。
- `docs/release-notes-0.2.7.md:28-35` — 0.2.6 相当へ戻す機能としての説明（補助資料）。

# `STRATA_FUSE_HEAD_GR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

最終層の hyper-connection residual write と head 側の mixer read を `fused_gr_read_multi()` にまとめる実験的な実装スイッチです。Verifier の通常経路と MTP drafter 経路の両方に読み取りがあります。コード上で確認できる効果は呼び出しと計算の統合であり、速度向上や数値的一致を保証する測定資料は見つかりませんでした。

## 値と判定

同じ名前でも、Verifier と MTP では判定方法が異なります。

| 経路 | 未設定 | 設定値の判定 | 空文字・例 |
|---|---|---|---|
| CUDA/HIP Verifier (`src/core/verify.cpp`) | 無効 | 先頭文字が `'1'` のときだけ有効 | `1`, `10`, `1abc` は有効。空文字、`true`, `2`, ` 1`, `0` は無効 |
| SYCL Verifier (`sycl/src/core/verify.cpp`) | 無効 | CUDA/HIP Verifier と同じく先頭文字が `'1'` のとき有効 | 同上 |
| MTP drafter (`src/core/mtp.cpp`, `sycl/src/core/mtp.cpp`) | 無効 | `std::atoi(value) != 0` なら有効 | `1`, `2`, `-1`, ` 1x` は有効。空文字、`true`, `0abc` は無効 |

Verifier は値全体を parse せず、1文字目だけを比較します。MTP の `atoi` は先頭の空白と符号を許容し、数値変換できた先頭部分を使います。いずれも関数内 `static const bool` に保存されるため、それぞれの経路で最初に判定された後の環境変更は反映されません。

## 有効になる条件

- Verifier では設定値に加え、処理対象が全層を含むこと（`le_ == g.n_layers`）、`head_` が存在して読み込み済みであること、最後の層を cvec がカバーしないことが必要です。層分割の途中段では有効になりません。
- Verifier の最終 head 処理では、`mix_q8` 条件（head 読み込み済みで、output HC down/up に Q8 版がある）が有効なら、環境変数による fused write 分岐より先に Q8 mixer が選ばれます。
- MTP drafter は同じフラグが有効なら、最終 mixer と GR write をまとめる分岐を選びます。無効時は通常の GR write の後に head-mix multi または通常の read を行います。
- CUDA/HIP の実装は `src/`、SYCL は `sycl/` に別実装があります。Verifier の値判定は両 backend で同じですが、実行されるカーネル実装は各 backend のビルドに依存します。

## 実行時の詳細

Verifier の通常経路では、最終層の MoE combine 後に行う `gr_write` / `gr_write_multi` をフラグ有効時に省略します。全層終了後、fused 引数に残差、最終層の block output と injection、output HC mixer の重みを設定して `fused_gr_read_multi()` を呼び、GR write と head mixer read をまとめます。その後の head logits 計算と token 選択は通常の処理に続きます。Q8 mixer が選ばれた場合はそちらの経路が優先され、ここでの fused write は使われません。

MTP drafter では、`record_rest()` の MoE combine 後に通常の GR write をスキップし、`fused_gr_read_multi()` に draft の最終 mixer、combine 出力、injection を渡します。生成された `sample_` は次段の token 選択に使われます。

環境変数を読み取るだけのログ出力は見当たりません。値が無効、または Verifier の追加条件を満たさない場合は通常経路を使います。

## 根拠

- CUDA/HIP Verifier の判定・有効条件: `src/core/verify.cpp:1552-1558`。最終層 write の省略: `src/core/verify.cpp:1675-1684`。Q8 優先、fused 処理と fallback: `src/core/verify.cpp:1703-1767`。
- SYCL Verifier の判定・有効条件: `sycl/src/core/verify.cpp:1411-1417`。write の省略: `sycl/src/core/verify.cpp:1519-1528`。head 処理: `sycl/src/core/verify.cpp:1551-1615`。
- CUDA/HIP MTP の判定: `src/core/mtp.cpp:854-857`。通常 write の分岐と fused mixer: `src/core/mtp.cpp:925-965`。
- SYCL MTP の判定: `sycl/src/core/mtp.cpp:989-992`。通常 write の分岐と fused mixer: `sycl/src/core/mtp.cpp:1072-1105`。
- `docs/DETAILS.md` を含む `docs/` の Markdown に、この変数の挙動や測定値の説明は見つかりませんでした。

# `STRATA_FUSED_SWIGLU_Q81`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有ソース。外部ライブラリやドライバーが独自に読む環境変数の意味は扱わない。

## 役割

共有 expert の `SwiGLU(gate, up)` 計算と、その結果の Q8_1 量子化を融合したカーネル経路を選びます。既定では有効です。有効な場合、gate/up の射影結果から SiLU(gate) × up を計算し、その場で Q8_1 にして down 射影へ渡します。無効にすると、SwiGLU 計算と Q8_1 量子化を別々に実行します。

CUDA と SYCL の Strata エンジンに同じ判定があります。単一トークン用の `shared_expert()` と、検証時の複数トークン用 `shared_expert_multi()` が対象です。これは共有 expert の GPU カーネル選択であり、環境変数を読むだけの診断フックではありません。

## 値と判定

値全体の比較ではなく、`std::atoi()` の戻り値が 0 かどうかで判定します。未設定なら有効、設定済みなら `atoi(value) != 0` のとき有効です。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| `1`、`2`、`-1` | 有効（変換結果が 0 以外） |
| `0`、`00`、`0tail` | 無効（先頭の数値部分が 0） |
| 空文字、`true`、`false`、`tail` | 無効（変換できる先頭の数値がなく、`atoi()` は 0 を返す） |
| ` 1tail`、`+1tail` | 有効（先頭の空白を読み飛ばし、10進数の数値部分を変換） |

文字列全体の妥当性検査、末尾文字の検査、大文字小文字の検査はありません。値は helper 内の `static const bool` に初回評価結果として保存されます。そのプロセスで最初に共有 expert の該当関数がこの判定を通った後に環境を変更しても、再評価されません。

根拠: CUDA `src/kernels/cuda/shared_expert.cu:205-210`、SYCL `sycl/src/kernels/cuda/shared_expert.dp.cpp:304-309`。

## 有効になる条件

単一トークン経路では、環境変数が有効であることに加え、共有 expert の gate/up/down のうち少なくとも一つが native 射影として利用可能で、down 射影も native として利用可能な場合に融合 Q8_1 経路を使います。したがって、gate/up がどちらも native でない場合や down が native でない場合は、この変数が有効でも融合経路には入りません。これらの場合、既存の SwiGLU・量子化処理へ進みます。

複数トークン経路では `shared_expert_multi()` が gate/up/down の native weight と Q8_1 workspace を前提条件として検査した後、この変数で融合カーネルと分離カーネルを選びます。呼び出し元は CUDA/SYCL の verifier で、共有 expert の各 weight が native 形式にできないとその前段で失敗します。

ビルド条件は CUDA エンジンまたは SYCL エンジンです。HIP 向けにこの環境変数を読む実装は検索した Strata ソース内で見つかりませんでした。共通の既定値切替ログはありません。

根拠: CUDA `src/kernels/cuda/shared_expert.cu:285-299,333-374`、`214-240`、`src/core/verify.cpp:1511-1535`。SYCL `sycl/src/kernels/cuda/shared_expert.dp.cpp:488-500,535-595`、`313-335`、`sycl/src/core/verify.cpp:1370-1394`。

## 実行時の詳細

`shared_expert()` は gate と up の射影結果を得た後、native projection と native down が使え、かつ環境変数が有効なら `native_swiglu_quantize_q8_1()` を呼び、その出力を使って native down 射影を実行します。無効、または必要な native 条件を満たさない場合は、SwiGLU カーネルで中間値を作り、down が native なら別途 `native_quantize_q8_1()` を実行します。down も native でなければ、down weight の形式に応じた既存の量子化・射影経路を使います。

`shared_expert_multi()` は有効時に全 token の SwiGLU と Q8_1 量子化を `native_swiglu_quantize_q8_1()` に渡します。無効時は `native_swiglu_kernel`、続いて `native_quantize_q8_1()` を実行してから、どちらの場合も native down 射影を行います。この関数は 1〜8 token を受け付け、verifier がその時点の token 数 `n` を渡します。

融合カーネルが行う演算の意図は `SiLU(gate) * up` です。CUDA の別カーネル実装では `__fdividef(gate, 1 + __expf(-gate)) * up` と明記されています。切替による速度差や数値同一性を裏付ける測定値は、この環境変数を対象にした `docs/` 内の記述から確認できなかったため、ここでは記載しません。

根拠: CUDA `src/kernels/cuda/shared_expert.cu:53-70,333-374`、`214-240`。SYCL `sycl/src/kernels/cuda/shared_expert.dp.cpp:333-365,535-595`。

## 根拠

- 候補名は `000_envvers.md` に記載されています。
- 環境変数の読み取りは CUDA `src/kernels/cuda/shared_expert.cu:205-210` と SYCL `sycl/src/kernels/cuda/shared_expert.dp.cpp:304-309` の各一箇所です。
- `shared_expert()` の通常層経路への接続は `src/core/layer.cpp:437-453` にあります。
- `shared_expert_multi()` の verifier 経路への接続は `src/core/verify.cpp:1511-1540` と SYCL `sycl/src/core/verify.cpp:1370-1400` にあります。
- `docs/` にこの変数を直接説明する記述は見つかりませんでした。

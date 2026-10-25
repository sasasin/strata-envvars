# `STRATA_TOPK_ACTIVE_ANY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の prompt prefill で、実際に使うブロック数（`active_blocks`）を使った top-k dispatch を、Turing（sm_75）以外の CUDA GPU にも強制します。通常の CUDA 実行ではこの dispatch は Turing のみを対象にしています。名前に `ANY` とありますが、後述のとおり有効値は `1` で始まる文字列に限られます。

これは通常の利用者向け設定というより、全 CUDA カードで同じ dispatch を検証するためのフックです。CMake は `qsa_topk_active_parity` をテストとして登録し、そのテスト自身がこの変数を `1` に設定します。製品コード側にも読み取り箇所があるため、テスト以外の CUDA 実行で設定すれば dispatch に影響します。

## 値と判定

実装は文字列を数値変換せず、値の先頭文字が `'1'` かどうかだけを検査します。

| 値 | `any_card` |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1` など、先頭文字が `1` でない値 | 無効 |

CUDA 実装では `qsa_block_topk()` 内の `static const bool` に保存されるため、環境変数は関数がこの判定箇所に初めて到達した時に一度だけ評価されます。その後の同一プロセス内の変更は反映されません。`nq <= 0` の呼び出しや、先行する cluster kernel が処理して戻る呼び出しでは、この判定箇所に到達しないことがあります。

## 有効になる条件

CUDA では、`STRATA_TOPK_CAPACITY_GUARD` が**設定されていない**こと、`active_blocks > 0` かつ `active_blocks <= max_blocks` であることが必要です。そのうえで、通常は実行 GPU が sm_75 の場合に active-block dispatch が使われます。この変数が有効なら GPU 世代の条件を満たしたものとして扱います。`STRATA_TOPK_CAPACITY_GUARD` は値の内容を問わず、設定されているだけで active-block dispatch を抑止します。

`active_blocks` を渡している本番呼び出しは prefill の QSA 選択です。decode の `qsa_block_topk()` 呼び出しや verify の呼び出しはこの引数を省略するため、通常の経路ではこの変数による dispatch 変更は起きません。CUDA の HIP ビルドではコードが別分岐になり、この変数は読み取られません。

## 実行時の詳細

prefill は各 query batch の最後の query から `active = n_bid + 1` を求め、QSA block top-k に渡します。active-bound dispatch が選ばれると、実際に有効なブロック数を使って `reach` と register kernel の適用範囲を判断します。条件により reference kernel、register kernel、wide kernel の選択が変わります。score 行の stride と top-k kernel に渡す `max_blocks` は引き続き capacity の値です。GPU 世代別の `active_blocks` 取得条件を変えるものであり、値そのものや top-k の設定値を変える変数ではありません。

SYCL 用に生成・保守されている `sycl/src/kernels/cuda/qsa_select.dp.cpp` にも同じ環境変数判定と active-bound dispatch があります。SYCL ビルドは `qsa_select` を kernel 群に含めています。CUDA と SYCL のいずれの該当箇所にも、この変数専用のログ出力はありません。HIP は `active_blocks > 0` を直接 dispatch 条件にするため、この変数を使いません。

この分岐を検証する `qsa_topk_active_parity` は、capacity に基づく呼び出しと active count を渡す呼び出しの選択 ID を比較し、差があれば失敗する作りです。ソースには成功時の `PASS: 20 top-k active-bound cases, selected IDs bitwise identical` 出力がありますが、この調査ではテストを実行していません。

## 文書との照合

`docs/TROUBLESHOOTING.md` は、Turing の長い prompt で top-k の wide kernel を選び、`STRATA_TOPK_STREAM=0` で register kernel に戻せることを説明しています。これは関連する Turing prompt dispatch の説明ですが、`STRATA_TOPK_ACTIVE_ANY` 自体の値や用途は記載していません。現行コードではこの変数はカード選択条件を強制し、wide/register の選択は active count や `STRATA_TOPK_STREAM` などに基づいて別途行われます。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1295-1328` — 変数の読み取り、値判定、容量 guard と Turing 判定との組み合わせ、`reach` の決定。
- `src/kernels/cuda/qsa_select.cu:1334-1362` — active count を使う kernel dispatch と fallback。
- `src/kernels/cuda/qsa_select.cu:1211-1227` — 通常の CUDA dispatch が sm_75 を判定する処理。
- `src/prefill/prefill.cpp:2760-2775` — prefill で active count を計算し、top-k に渡す箇所。
- `src/core/layer.cpp:1122-1131`, `src/core/verify.cpp:1367-1384` — decode / verify 呼び出しで active count を渡さない箇所。
- `src/kernels/qsa_topk_active_parity.cpp:41-55,74-95`, `CMakeLists.txt:392-399` — 検証テストの設定、比較、出力、および CUDA テストとしての登録。
- `sycl/src/kernels/cuda/qsa_select.dp.cpp:1953-1986`, `sycl/CMakeLists.txt:205-216` — SYCL 側の同等実装と kernel 登録。
- `docs/TROUBLESHOOTING.md:93-95` — 関連する Turing prompt dispatch の説明。

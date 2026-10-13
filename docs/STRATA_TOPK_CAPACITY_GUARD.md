# `STRATA_TOPK_CAPACITY_GUARD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA block top-k 選択で、prefill の active block 数を使う dispatch を無効にし、capacity（`max_blocks`）を使う既存の dispatch に戻します。主な影響先は Turing（compute capability 7.5）上の prefill です。選択 kernel の dispatch 条件を変えるフックであり、スコアや top-k の計算式を直接変えるコードではありません。

## 値と判定

| 環境変数の状態 | `capacity_guard` |
|---|---:|
| 未設定 | `false` |
| 任意の値を設定 | `true` |
| 空文字を設定 | `true` |

実装は `std::getenv(...) != nullptr` のみを評価し、文字列の内容、数値、大文字小文字は読みません。したがって `=0` でも guard は有効です。

判定結果は `qsa_block_topk()` 内の関数ローカル `static const bool` に保存されます。CUDA cluster kernel が成功して先に return する呼び出しではこの宣言に到達しません。宣言に初めて到達した時点で値が確定し、その後の環境変更は反映されません。

## 有効になる条件

- `src/kernels/cuda/qsa_select.cu` の CUDA 実装が対象です。HIP コンパイルでは `#if !defined(__HIPCC__)` の外にあり、この環境変数は参照されません。
- guard が無効でも、active-count dispatch が使われるには `active_blocks > 0`、`active_blocks <= max_blocks`、かつ Turing デバイスであることが必要です。`STRATA_TOPK_ACTIVE_ANY=1` はテスト用にデバイス条件を迂回しますが、`capacity_guard` が有効なら active-count dispatch は引き続き無効です。
- 通常のprefillは選択 batch の最終 query の `n_bid + 1` を `active_blocks` として渡します。decode の呼び出しは active count を渡さず、captured graph / verify の呼び出しもこの値を省略しています。その場合、guard の有無で active-count dispatch は変わりません。
- CUDA cluster kernel が適用できて先に成功した呼び出しでは、その cluster dispatch が優先され、この guard の値は参照されません。

## 実行時の詳細

prefill は `active_blocks` を `qsa_block_topk()` に渡します。guard が無効で値が正かつ容量以下、さらに（`STRATA_TOPK_ACTIVE_ANY` によるテスト指定がなければ）GPU が Turing のとき、`counted` が真になり、選択の到達範囲 `reach` は `min(active_blocks, max_blocks)` になります。guard が有効なら `counted` は偽となり、`reach` は `max_blocks` です。ここで `max_blocks` は状態の容量です。

この `reach` は後続の kernel 選択に使われます。範囲が register kernel の `fit` を超えると CUDA は wide kernel を選び、そうでなければ register kernel のいずれかを使います。active-count の有無により小規模ケースの reference kernel への fallback 条件も評価されます。従って guard は単に active count の読み取りを止めるのではなく、capacity 基準に戻すことで kernel dispatch を変えることがあります。

コードコメントは Turing prefill が capacity 上限ではなく active block 上限を使う設計、および `STRATA_TOPK_STREAM` と連動する wide kernel の分岐を説明しています。`STRATA_TOPK_CAPACITY_GUARD` 自体について、専用ログや警告を出す実装は見つかりませんでした。既存資料 `docs/DETAILS.md` の環境変数一覧には `STRATA_TOPK_STREAM` の記載がありますが、この guard の説明は確認できませんでした。

SYCL 側の `sycl/src/kernels/cuda/qsa_select.dp.cpp` にも同名のコードがありますが、ファイル先頭に CUDA ソースからのDPCT変換物である旨が示されています。本調査では生成・変換済みコードを実装根拠にせず、CUDAネイティブ実装を根拠としました。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1211-1226` — HIPを除くTuring判定。device property の major/minor が 7.5 であることを確認し、calling thread ごとにdevice判定をcache。
- `src/kernels/cuda/qsa_select.cu:1295-1327` — cluster経路、環境変数の存在判定、active count による `counted` / `reach` の決定。
- `src/kernels/cuda/qsa_select.cu:1330-1362` — reference、wide、register kernel のdispatchと実行エラー時のstderr出力。
- `src/prefill/prefill.cpp:2760-2775` — prefill batch の最終 query から `active_blocks` を求め、top-k関数へ渡す箇所。
- `src/core/layer.cpp:1122-1131` — decode 側は `qsa_block_topk()` に active count を渡していない。
- `src/core/verify.cpp:1370-1384` — verify側のtop-k呼び出しも active count を省略。
- `docs/DETAILS.md:278-280` — 関連する `STRATA_TOPK_STREAM` の記載。guard の説明は掲載されていない。

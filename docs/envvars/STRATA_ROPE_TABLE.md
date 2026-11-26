# `STRATA_ROPE_TABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA native RoPE、QSA indexer、および CUDA prefill の RoPE が、セッションで作成された cos/sin テーブルを回転角に使うかを切り替える。未使用時は各カーネルが従来の `powf` と scaling 計算から角度を求める。通常の RoPE 計算自体を無効化する変数ではない。実読み取りとテーブル選択は `engine/src/kernels/cuda/native_rope.cu:156-176` と `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:206-226` にある。

## 値と判定

両実装とも `std::getenv` の戻り値が null でなく、先頭 1 文字が `'1'` の場合だけ有効とする。文字列全体の比較や数値変換はしない。したがって未設定、空文字、`0`、`true`、先頭が空白の ` 1`、`01` は無効で、`1`、`10`、`1anything` は有効になる。大小文字の概念はなく、後続文字は無視される（`engine/src/kernels/cuda/native_rope.cu:157-163`; SYCL 側: `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:207-213`）。

テーブルの有効化に対する CLI 引数や別環境変数の優先順位はない。設定が有効でも、呼び出し側に適合する登録テーブルがなければカーネルは通常の角度計算へフォールバックする（`engine/src/kernels/cuda/native_rope.cu:173-176`; `engine/src/prefill/kernels.cu:3544-3552`）。

## 有効になる条件

- 初期化した QSA state が共有テーブルを借りるのでなく自身で作成し（`share_rope == nullptr`）、かつ `s.n_rot == 64` の場合にだけ、この RoPE テーブルを登録する。通常 CUDA と SYCL の実装に同じ条件がある（`engine/src/core/layer.cpp:965-973`; `engine/sycl/src/core/layer.cpp:950-962`）。テーブルは state 初期化時に host 側で作成され、デバイスへコピーされる。
- 登録テーブルは現在の device ごとに選ばれ、要求された `RopeScaling` が登録時と全項目一致しなければ利用されない（`engine/src/kernels/cuda/native_rope.cu:145-176`; SYCL 側: `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:195-226`）。
- テーブル参照は `0 <= p < max_pos` の位置に限られる。範囲外は角度をその場で計算する（`engine/include/strata/kernels/mrope.hpp:54-60`）。
- 実読み取りは通常 CUDA の native RoPE 実装と、SYCL ツリー内の CUDA native RoPE 実装にある。これらが登録テーブルを照会し、CUDA/SYCL の prefill と QSA indexer も同じ照会関数を通る（例: `engine/sycl/src/prefill/kernels.dp.cpp:3244`; `engine/sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:398,489`）。候補名の他のソース参照はコメントまたは設定登録データであり、別の `getenv` 読み取りではない。
- Metal、CPU 等がこのフラグを直接読む実装は確認できなかった。ここで追跡した適用範囲は、明示的に読み取りがある native CUDA RoPE と、そのテーブルを選択する CUDA prefill / QSA indexer 呼び出し経路である。

## 実行時の詳細

読み取り結果は `rope_table_enabled()` 内の関数ローカル `static const bool` に保持される。各実装のプロセス内で初回呼び出し時に一度評価され、その後に環境を変更しても反映されない（`engine/src/kernels/cuda/native_rope.cu:157-163`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:207-213`）。

フラグが有効で適合テーブルがある場合、host 側は `RopeTab` を取得して `<true>` カーネルを起動する。native RoPE と RMS+RoPE、prefill、QSA indexer はその表から cos/sin を読み、表が使えない場合には `<false>` カーネルが従来の計算経路を使う（CUDA: `engine/src/kernels/cuda/native_rope.cu:212-220,238-246`; `engine/src/kernels/cuda/native_qsa_indexer.cu:286-298`; `engine/src/prefill/kernels.cu:3542-3553,3567-3578`; SYCL: `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:262,352`; `engine/sycl/src/prefill/kernels.dp.cpp:3244`; `engine/sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:398,489`）。表の有効時と無効時では回転に使う値が変わり得る。コメントは float64 由来の表と fast-math 計算の最下位ビット差に言及しているが、性能や生成結果の測定値はこのソースからは確認できない（`engine/src/kernels/cuda/native_rope.cu:145-156`）。

この変数専用のログ、警告、終了経路はない。適合テーブルがない場合は通常の計算へフォールバックする。カーネル起動後の CUDA エラーは既存の `cudaGetLastError()` 処理で例外になるが、これはこの変数固有のエラーではない（`engine/src/kernels/cuda/native_rope.cu:221-222,247-248`）。

## ログと測定値

該当なし。このフラグに関する実行時ログはなく、コード上の測定値もない。

## 根拠

- 読み取り、cache、登録テーブル照合: `engine/src/kernels/cuda/native_rope.cu:145-176`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:195-226`
- テーブル生成と登録条件: `engine/src/core/layer.cpp:961-973`; `engine/sycl/src/core/layer.cpp:946-962`
- native RoPE / indexer / prefill のテーブル分岐: `engine/src/kernels/cuda/native_rope.cu:209-222`; `engine/src/kernels/cuda/native_qsa_indexer.cu:286-298`; `engine/src/prefill/kernels.cu:3542-3553`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:262,352`; `engine/sycl/src/prefill/kernels.dp.cpp:3244`; `engine/sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:398,489`
- テーブルの位置範囲: `engine/include/strata/kernels/mrope.hpp:54-60`

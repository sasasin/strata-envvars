# `INK_METAL_MAX_BUF_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal バックエンドがモデルを Metal バッファへ wrap するとき、Section 4 を分割する各バッファの上限を MiB 単位で指定する。コード上の実効値は指定値から計算した上限と `mtl::Context::max_buffer_length()` の小さい方で、Section 4 を最大 4 個のページ境界付きバッファに分ける。モデルの重みや選択、生成設定を変える変数ではない。Section 1 のバッファ長にはこの指定値を使わず、ハードウェア上限で処理する（`engine/src/inkling2/metal/ink_metal_common.h:478-500,502-532`）。

## 値と判定

`wrap_model_buffers()` の呼び出しごとに `std::getenv` で読み、設定されていれば `std::strtoull(ev, nullptr, 10)` で符号なし整数へ変換する。末尾まで解析できたか、`errno` が立ったかは検査しない。変換結果が 256 未満なら無視し、256 以上なら `mb << 20` を 16 KiB 境界へ切り下げた値を上限候補にする。シフトは `uint64_t` 上で行われるため、大きすぎる値は unsigned の折り返しが起きる。変換後の候補がハードウェア上限より小さいときだけ実効上限を下げる（`engine/src/inkling2/metal/ink_metal_common.h:480-490`）。

| 条件 | unset | 受け付けられる例 | 無視または別の結果になる例 |
| --- | --- | --- | --- |
| すべての Metal 読み込み経路 | `hw_max_buf` を使用 | `256` は 256 MiB、`4096` は 4096 MiB の候補上限 | 空文字、`0`、`1`、`255`、`true`、`false`、`0anything` は変換値が 256 未満となり無視 |
| 10 進数の先頭部分が 256 以上 | ハードウェア上限 | `256anything` は 256 として扱う。先頭空白や `+` 付き数値も `strtoull` の規則で数値化される | `256` 未満の数値に続く文字列は値を有効にしない。全体一致や真偽値の判定はしない |

`-1` のような負数も拒否せず、`strtoull` が符号なし値に変換します。負数や上限を超える数値について、コードは範囲エラーとして報告しません。変換後のシフト折り返しを含む値から候補上限を計算し、最後にハードウェア上限と比較します（`engine/src/inkling2/metal/ink_metal_common.h:484-489`）。

## 有効になる条件

- Strata の Apple Silicon Metal バックエンドがモデル読み込みに到達すること。Metal backend は `engine/src/inkling2/metal/ink_metal_backend.mm` を含む Metal ターゲットとして定義される（`engine/src/inkling2/metal/CMakeLists.txt:1-5,27-30`）。
- `.strata` の `load()` と、`INK_METAL_WITH_MODEL_FILE` が有効な backend の `load_from_model_file()` は、どちらも Section 4 を Metal バッファへ wrap する共通関数を呼ぶ。したがってモデルファイル形式の選択でこの変数の適用は外れない（`engine/src/inkling2/metal/ink_metal_common.h:448-458,572-575,747-749`; `engine/src/inkling2/metal/ink_metal_backend.mm:14-15,98-103`）。
- 算出値が `hw_max_buf` より小さい場合に限り、Section 4 の分割サイズを実際に下げる。大きい値はハードウェア上限を増やさず、256 未満や変換結果が 0 の値も上限を下げない（`engine/src/inkling2/metal/ink_metal_common.h:482-490`）。
- Section 4 の各 chunk には、最大 expert body を含められる overlap が必要で、`eff_max_buf <= overlap` なら設定値の有無にかかわらず読み込み関数は失敗する。また Section 4 が 4 chunk を超える場合も失敗する（`engine/src/inkling2/metal/ink_metal_common.h:502-524`）。
- CLI 引数による上書きはない。`INK_METAL_FORCE_MODEL_FILE` は Metal backend 内で読み込み経路を選ぶが、どちらの経路も共通 wrap 関数へ進む（`engine/src/inkling2/metal/ink_metal_backend.mm:98-103`; `engine/src/inkling2/metal/ink_metal_common.h:457-458,747-749`）。

## 実行時の詳細

読み取りは Metal モデル読み込み時に `wrap_model_buffers()` が呼ばれるたびに行われ、値の static cache はない。プロセス中に環境値を変えた場合、その後に呼ばれる読み込みでは再評価される（`engine/src/inkling2/metal/ink_metal_common.h:480-490`; 呼び出し元は `448-458,747-749`）。

Section 4 の範囲をページ境界にそろえ、`eff_max_buf` 以下の chunk を作る。各 chunk は後続の expert body を収めるよう overlap を持ち、expert ごとの buffer 内 offset と chunk 番号を割り当て直す。Section 1 は `hw_max_buf` と比較して wrap し、`eff_max_buf` を参照しない（`engine/src/inkling2/metal/ink_metal_common.h:492-500,502-560`）。

成功時は chunk が複数あるか `eff_max_buf < hw_max_buf` の場合に限り、stderr に `[ink_metal] split-buffer sec1=... + sec4=... across ... Metal buffers (effMaxBuf=..., overlap=...)` を出す。失敗条件では関数が `false` を返し、単体 Metal 実行ファイルは `[ERROR] load: <理由>` を stderr に出して終了コード 1 を返す。具体的な理由文字列は `INK_METAL_MAX_BUF_MB too small for expert size`、Section 4 が 4 バッファを超えた場合の `Section 4 (...) exceeds 4 Metal buffers of ... MiB each`、wrap 後に expert を chunk に置けない場合の `expert ... does not fit any Metal sec4 buffer chunk` など（`engine/src/inkling2/metal/ink_metal_common.h:510-560,563-568`; `engine/src/inkling2/metal/ink_metal_main.cpp:481-485`）。backend 経路ではモデル読み込み失敗を `init()` が呼び出し元へ返す（`engine/src/inkling2/metal/ink_metal_backend.mm:92-103`）。

`docs/DETAILS.md` と Metal 関連資料に、この変数固有の値域や性能測定値は見当たらないため、性能効果は記載しない。

## ログと測定値

この変数固有の測定値は該当資料にない。上記の split-buffer 成功ログは stderr に出る条件付きの観測結果であり、unset で chunk が 1 個、かつハードウェア上限を下げない場合には出ない（`engine/src/inkling2/metal/ink_metal_common.h:563-568`）。

## 根拠

- 直接の環境読み取り、数値変換、実効上限: `engine/src/inkling2/metal/ink_metal_common.h:480-490`
- Section 1 と Section 4 の wrap、chunk 数、expert remap、失敗理由とログ: `engine/src/inkling2/metal/ink_metal_common.h:492-568`
- `.strata` 読み込みでの共通関数呼び出し: `engine/src/inkling2/metal/ink_metal_common.h:448-458`
- `InkModelFile` 読み込みと共通関数呼び出し: `engine/src/inkling2/metal/ink_metal_common.h:572-575,747-749`
- Metal backend の読み込み経路と失敗伝播: `engine/src/inkling2/metal/ink_metal_backend.mm:14-15,92-103`
- 単体実行ファイルの load 失敗表示と終了: `engine/src/inkling2/metal/ink_metal_main.cpp:481-485`
- Metal ターゲット定義: `engine/src/inkling2/metal/CMakeLists.txt:1-5,27-30`

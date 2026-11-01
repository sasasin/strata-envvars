# `DS4_MM_NOGU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DSV41 の prompt chunk 用 i-quant expert GEMM で、gate/up 行列積カーネルの dispatch を省略するフックです。コード上、この名前をモデル設定や CLI 引数として読む箇所はありません。値の内容ではなく、環境変数が設定されているかを判定します。

`DS4_MM_NOGU` は `gate_up == true` のときだけ選ばれます。同じ判定箇所は down 側では別名 `DS4_MM_NODN` を選びます。

## 値と判定

| 環境の状態 | 判定 |
|---|---|
| 未設定 | gate/up カーネルを通常どおり dispatch する |
| 設定あり（空文字を含む） | gate/up カーネルを dispatch せず、`mm_set()` は `true` を返す |

値の文字列比較・数値変換はありません。`DS4_MM_NOGU=0` や空文字も「設定あり」と同じ扱いです。値の範囲、不正値、境界値という区別はありません。判定は `mm_set()` の呼び出しごとに行われ、`static` cache には保存されません。

## 有効になる条件

- `STRATA_METAL` 定義を含む Metal ビルドであること。`set_gate_up()` はこの macro の下でのみ Metal host 関数を呼び、Metal ターゲットは `STRATA_METAL=1` を定義します。
- DSV41 の i-quant expert set の gate/up 経路で、呼び出し元が `hbounds != nullptr` を渡すこと。
- `mm_set()` が環境変数判定まで到達すること。たとえば正の expert 数・行数、対応する block size、次元・leading dimension 条件、Metal pipeline の準備、および必要な host view が満たされない場合は Metal 関数が `false` を返し、呼び出し元は backend の通常 kernel 経路へ続きます。`mm_set()` の主な寸法条件は `n_embd` と `n_ff` が 256 の倍数、`ldh == n_ff` です。
- gate/up 以外の down 経路ではこの名前は選ばれません。down カーネルを省略する別の名前は `DS4_MM_NODN` です。

CUDA/HIP 専用ビルドではこの Metal host 分岐に入りません。モデルが通常生成できるか、prompt 経路以外に影響するかを示す CLI 優先順位や追加の環境変数は、この読み取り箇所にはありません。

## 実行時の詳細

Metal の `mm_set(true, ...)` は、環境判定より前に kernel pipeline と scratch を準備し、gate/up 側では入力行の gather dispatch も行います。その後、`DS4_MM_NOGU` が設定されていれば tile buffer を解放して `true` を返し、gate/up の行列積 dispatch を行いません。呼び出し元の `set_gate_up()` はこの `true` を「Metal が処理した」とみなし、通常の CUDA kernel 経路にフォールバックしません。

したがって、この変数を設定すると gate/up 出力 `h` はこの関数では計算されません。呼び出し元は通常どおり次の down 処理へ進みますが、この分岐はエラーや警告を出さず、未計算出力を検出する処理も示していません。後続の結果は正しいモデル出力として保証されません。この変数による専用ログ、終了コード変更、失敗メッセージはありません。

値は `getenv()` により各 `mm_set()` 呼び出し時に読みます。Strata 内でこの変数を別の値に書き換える箇所や、子プロセスへ個別に転送する箇所は確認できません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2484,2513-2527`: `mm_set()` の入口、寸法条件、pipeline 準備と失敗時の `false`。
- `metal/src/engine/ds4_finish.cpp:2534-2558,2559-2574`: gate/up 用 scratch 準備と環境判定前の gather dispatch。
- `metal/src/engine/ds4_finish.cpp:2614-2618`: `gate_up` に応じた環境名の選択、設定有無による dispatch のスキップと `true` 返却。
- `src/dsv41/ds4_iq.cu:1585-1601`: Metal host 呼び出しを `STRATA_METAL` 条件で行い、成功時に通常 kernel 経路へ進まない実装。
- `metal/CMakeLists.txt:165-171`: Metal DSV41 target の `STRATA_METAL=1` 定義と Metal host/kernel のリンク。
- `src/dsv41/ds4_gguf.cu:1575-1592,1637-1652` および `src/dsv41/ds4_model.cu:4255-4259`: low-bit expert set の gate/up と down を順に呼び、gate/up 成功後も down へ進む呼び出し経路。

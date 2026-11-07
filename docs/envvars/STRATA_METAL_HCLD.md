# `STRATA_METAL_HCLD`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal decode window の hyper-connection (HC) down/up カーネルで、Q8_0 重みを扱う場合に複数 unit のロードと計算をまとめる variant を選びます。既定は無効です。`1` にすると該当する Q8_0 経路が prefetch variant を dispatch します。Metal 専用実装であり、CUDA/HIP/SYCL の設定ではありません。

対象の dispatch は各 layer の attention HC、FFN HC、および output HC の read から呼ばれます。ただし変数が選択を変えるのは、down と up の重みがともに Q8_0 相当として扱われる場合です。その他の重み形式では従来 variant のままです。

## 値と判定

`Window::gr_read()` 内の関数局所 `static const bool` として初回に一度判定し、その後は結果を cache します。環境変数の文字列全体が厳密に `"1"` と等しい場合だけ有効です。

| 環境値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`true`、`01`、`1 `、その他の文字列 | 無効 |

数値変換、trim、大文字小文字変換、範囲補正はありません。CLI 引数や別の環境変数による上書きはこの読み取り箇所にはありません。

## 有効になる条件

- macOS 向け Metal engine の decode window が使用されること。Metal build は `metal/CMakeLists.txt` で Apple のみを許し、`STRATA_METAL_ENGINE` が ON の場合に engine を含めます (`metal/CMakeLists.txt:1-2,16-18,73-77`)。
- `Window::gr_read()` が実行されること。layer の attention HC / FFN HC と output HC で呼び出されています (`metal/src/engine/window.cpp:1056-1060,1191-1194,1531-1534`)。
- down (`tdn`) と up (`tup`) の両方が Q8_0、または Q8_0 へのロード時コピー (`q8off_`) として認識されること (`metal/src/engine/window.cpp:982-993`)。

down/up がともに Q8_0 のとき、設定値 `1` は down の `gr_downp_q8_8_8` と up の `gr_upp_q8` を選択します。それ以外の値は `gr_down_q8_8_8` と `gr_up_q8` を選びます。down は Q8_0、inject が F32 の場合には `gr_downp_q8f_8_8` / `gr_down_q8f_8_8` を同様に切り替えます。down/up が Q8_0 でない場合は down が `gr_down_8_8`、up が `gr_up` で、変数は variant 選択に影響しません (`metal/src/engine/window.cpp:982-1005`)。

## 実行時の詳細

環境値を読むのは `gr_read()` が初めて呼ばれたときです。読み取り結果は `static const bool hcld` に保存され、同一プロセスで環境値を後から変えても再評価されません。変数の値自体によるログや警告はありません。

選択される既定 variant は `grd_acc()` / `gr_up_f<..., 0>`、有効時の variant は `grd_acc_p()` / `gr_up_f<..., 1>` を使います。down の prefetch variant は lane ごとに 2 unit 分を decode してから順に積算し、端数を通常ループで処理します。up variant は最大 3 unit を decode してから元と同じ順序で積算します。カーネル内コメントは加算順が従来 variant と同じで bitwise 同一と説明しています (`metal/kernels/gr.metal:100-147,149-190,192-225`)。

variant は全体の `gr.metal` library に含まれます (`metal/src/engine/window.cpp:728-730`, `metal/kernels/gr.metal:270-279`)。選択した関数が Metal library に存在しない場合、pipeline 作成時に `mtl: no function <name> ...` を stderr に出して終了コード 3 で終了します。pipeline state の作成に失敗した場合も `mtl: pipeline <name>: ...` を stderr に出し、終了コード 3 で終了します (`metal/src/engine/window.cpp:272-278`, `metal/src/mtl_rt.mm:484-521`)。列挙した variant は同梱カーネルで定義されているため、通常の同梱構成ではこの失敗経路に入りません。

実装行の注釈には、HCLD variant が M5 Max / UD-Q4_K_XL で 4 回の各 round において -10.9% だったため OFF とした記録があります (`metal/src/engine/window.cpp:995`)。これはソースコメントに記載された条件の測定値で、他の Mac、モデル、実行条件での性能を示すものではありません。`docs/DETAILS.md` にはこの変数の説明は見つかりませんでした。

## 根拠

- 直接の環境読み取り、値比較、static cache、dispatch 名選択: `metal/src/engine/window.cpp:982-1005`
- 呼び出し経路: `metal/src/engine/window.cpp:1056-1060,1191-1194,1531-1534`
- Q8_0 判定と inject F32 条件: `metal/src/engine/window.cpp:982-994`
- 従来 / prefetch カーネルの実装と同梱宣言: `metal/kernels/gr.metal:100-147,149-225,270-279`
- Metal build 条件とカーネル library への収録: `metal/CMakeLists.txt:1-2,16-18,73-77`; `metal/src/engine/window.cpp:728-730`
- pipeline 作成失敗時の stderr・終了経路: `metal/src/engine/window.cpp:272-278`; `metal/src/mtl_rt.mm:484-521`
